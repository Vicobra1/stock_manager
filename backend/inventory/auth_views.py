from django.contrib.auth import authenticate
from rest_framework import serializers, status
from rest_framework.exceptions import Throttled
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView


class UserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    is_staff = serializers.BooleanField()


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
        seconds = max(int(wait or 0), 1)
        raise Throttled(wait=wait, detail=f"Trop de tentatives de connexion. Réessayez dans {seconds} seconde{'s' if seconds > 1 else ''}.")

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(request=request, **serializer.validated_data)
        if user is None:
            return Response({"detail": "Identifiants invalides."}, status=status.HTTP_400_BAD_REQUEST)
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user": UserSerializer(user).data})


class LogoutView(APIView):
    """POST -> 204. Supprime le jeton : il ne fonctionne plus, sur tous les appareils."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    """GET -> l'utilisateur correspondant au jeton (permet de restaurer la session au rechargement de la page)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)
