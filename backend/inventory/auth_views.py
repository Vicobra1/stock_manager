import math

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework import serializers, status
from rest_framework.exceptions import Throttled
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .authentication import is_expired
from .models import Membership, Shop, ShopToken
from .quotas import create_shop
from .roles import get_role


class UserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    is_staff = serializers.BooleanField()
    role = serializers.SerializerMethodField()

    def get_role(self, user):
        # Rôle DANS la boutique du jeton ; aucun avec le jeton « compte » (il faut d'abord choisir une boutique).
        return get_role(self.context.get("request"))


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False)


def plural(count, word):
    return f"{count} {word}{'s' if count > 1 else ''}"


class FrenchThrottleMixin:
    """Message de blocage en français, sans la phrase ajoutée par DRF, et cohérent avec l'en-tête Retry-After."""
    throttle_message = "Trop de demandes. Réessayez dans {delay}."

    def throttled(self, request, wait):
        # Arrondi vers le haut, comme DRF, pour que le message et l'en-tête Retry-After donnent le même délai.
        seconds = max(math.ceil(wait or 0), 1)
        exc = Throttled(detail=self.throttle_message.format(delay=self.format_delay(seconds)))
        # wait est renseigné après coup : passé au constructeur, DRF ajouterait sa propre phrase au message.
        exc.wait = seconds
        raise exc

    def format_delay(self, seconds):
        return plural(seconds, "seconde")


class LoginView(FrenchThrottleMixin, APIView):
    """POST {username, password} -> {token, user}. Le même message d'erreur est renvoyé quel que soit le motif."""
    # Aucune authentification ici : un ancien jeton envoyé par erreur ne doit pas empêcher de se connecter.
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"
    throttle_message = "Trop de tentatives de connexion. Réessayez dans {delay}."

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(request=request, **serializer.validated_data)
        if user is None:
            return Response({"detail": "Identifiants invalides."}, status=status.HTTP_400_BAD_REQUEST)
        token, _ = Token.objects.get_or_create(user=user)
        if is_expired(token.created):
            # Jeton « compte » à durée fixe (décision D2) : une fois expiré, la connexion en donne un nouveau.
            token.delete()
            token = Token.objects.create(user=user)
        return Response({"token": token.key, "user": UserSerializer(user).data})


class LogoutView(APIView):
    """POST -> 204. Coupe tout (décision D2) : le jeton « compte » et tous les jetons de boutique de la personne."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        ShopToken.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    """GET -> l'utilisateur correspondant au jeton (permet de restaurer la session au rechargement de la page)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user, context={"request": request}).data)


def shop_summary(membership):
    return {"id": membership.shop.id, "name": membership.shop.name, "plan": membership.shop.plan,
            "role": membership.role}


class ShopNameField(serializers.CharField):
    """Nom de boutique unique, sans tenir compte des majuscules (décision D3b)."""

    def __init__(self, **kwargs):
        super().__init__(max_length=150, **kwargs)

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        if Shop.objects.filter(name_key=Shop.normalize_name(value)).exists():
            raise serializers.ValidationError(SHOP_NAME_TAKEN)
        return value


SHOP_NAME_TAKEN = "Une boutique porte déjà ce nom."
ONLY_MANAGERS_CREATE_SHOPS = "Seul un gérant peut créer une autre boutique."


class NewShopSerializer(serializers.Serializer):
    name = ShopNameField()


class MyShopsView(APIView):
    """GET -> mes boutiques et mon rôle dans chacune (choix de la boutique).

    POST {name} -> 201 : crée une boutique supplémentaire dont je deviens gérant, au plan gratuit (décision D6, B1).
    Réservé à une personne déjà gérante d'au moins une boutique : un vendeur ne peut pas créer de boutique.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        memberships = Membership.objects.filter(user=request.user).select_related("shop").order_by("shop__name")
        return Response([shop_summary(m) for m in memberships])

    def post(self, request):
        if not Membership.objects.filter(user=request.user, role=Membership.Role.MANAGER).exists():
            return Response({"detail": ONLY_MANAGERS_CREATE_SHOPS}, status=status.HTTP_403_FORBIDDEN)
        serializer = NewShopSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            shop = create_shop(serializer.validated_data["name"], request.user)
        except IntegrityError:  # même nom créé au même instant par quelqu'un d'autre
            return Response({"name": [SHOP_NAME_TAKEN]}, status=status.HTTP_400_BAD_REQUEST)
        return Response(shop_summary(shop.memberships.get(user=request.user)), status=status.HTTP_201_CREATED)


class ShopTokenSerializer(serializers.Serializer):
    shop = serializers.IntegerField()


class ShopTokenView(APIView):
    """POST {shop} -> 201 {token, expires_at, shop}. Second temps de la connexion (décision D2).

    Une boutique inexistante et une boutique dont on n'est pas membre donnent exactement la même réponse 404 :
    rien ne permet de deviner qu'une boutique existe.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ShopTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = (Membership.objects.select_related("shop")
                      .filter(user=request.user, shop_id=serializer.validated_data["shop"]).first())
        if membership is None:
            return Response({"detail": "Boutique introuvable."}, status=status.HTTP_404_NOT_FOUND)
        token = ShopToken.objects.create(user=request.user, shop=membership.shop)
        return Response({"token": token.key, "expires_at": token.expires_at, "shop": shop_summary(membership)},
                        status=status.HTTP_201_CREATED)


class SignupSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(trim_whitespace=False, write_only=True)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    shop_name = ShopNameField()

    def validate_username(self, value):
        get_user_model().username_validator(value)
        if get_user_model().objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Ce nom d'utilisateur est déjà pris.")
        return value

    def validate(self, attrs):
        # Règles de mot de passe de Django (décision D6, M1), y compris « trop proche du nom d'utilisateur ».
        candidate = get_user_model()(username=attrs["username"], first_name=attrs["first_name"],
                                     last_name=attrs.get("last_name", ""))
        try:
            validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})
        return attrs


class SignupView(FrenchThrottleMixin, APIView):
    """POST {username, password, first_name, last_name, shop_name} -> 201 {token, user, shop} (décision D6).

    Crée le compte et sa boutique (plan gratuit, la personne en est gérante), puis connecte directement : la réponse
    contient le jeton « compte », comme une connexion. Limité à 5 inscriptions par heure et par adresse IP.
    """
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "signup"
    throttle_message = "Trop d'inscriptions depuis cette adresse. Réessayez dans {delay}."

    def format_delay(self, seconds):
        return plural(math.ceil(seconds / 60), "minute") if seconds >= 60 else plural(seconds, "seconde")

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            with transaction.atomic():
                user = get_user_model().objects.create_user(data["username"], password=data["password"],
                                                            first_name=data["first_name"], last_name=data["last_name"])
                shop = create_shop(data["shop_name"], user)
        except IntegrityError:  # même nom de compte ou de boutique créé au même instant : rien n'est gardé
            return Response({"detail": "Ce nom d'utilisateur ou ce nom de boutique vient d'être pris."},
                            status=status.HTTP_400_BAD_REQUEST)
        token = Token.objects.create(user=user)
        return Response({"token": token.key, "user": UserSerializer(user).data,
                         "shop": shop_summary(shop.memberships.get(user=user))}, status=status.HTTP_201_CREATED)
