import math

from django.contrib.auth import authenticate
from rest_framework import serializers, status
from rest_framework.exceptions import Throttled
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .authentication import is_expired
from .models import Membership, ShopToken
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


class LoginView(APIView):
    """POST {username, password} -> {token, user}. Le même message d'erreur est renvoyé quel que soit le motif."""
    # Aucune authentification ici : un ancien jeton envoyé par erreur ne doit pas empêcher de se connecter.
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def throttled(self, request, wait):
        # Arrondi vers le haut, comme DRF, pour que le message et l'en-tête Retry-After donnent le même délai.
        seconds = max(math.ceil(wait or 0), 1)
        exc = Throttled(detail=f"Trop de tentatives de connexion. Réessayez dans {seconds} seconde{'s' if seconds > 1 else ''}.")
        # wait est renseigné après coup : passé au constructeur, DRF ajouterait sa propre phrase au message.
        exc.wait = seconds
        raise exc

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


class MyShopsView(APIView):
    """GET -> les boutiques dont la personne est membre, avec son rôle dans chacune (choix de la boutique)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        memberships = Membership.objects.filter(user=request.user).select_related("shop").order_by("shop__name")
        return Response([shop_summary(m) for m in memberships])


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
