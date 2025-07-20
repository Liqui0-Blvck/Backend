from django.contrib.auth import get_user_model
from rest_framework.authentication import BaseAuthentication
from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication

User = get_user_model()

class EmailAuthentication(BaseAuthentication):
    def authenticate(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        if not email or not password:
            return None
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise exceptions.AuthenticationFailed('No such user')
        if not user.check_password(password):
            raise exceptions.AuthenticationFailed('Incorrect password')
        if not user.is_active:
            raise exceptions.AuthenticationFailed('User inactive')
        return (user, None)

# Custom JWT authentication: busca el token en el header o en la cookie accessToken

class CustomJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        header = self.get_header(request)
        if header is not None:
            return super().authenticate(request)
        raw_token = request.COOKIES.get('accessToken')
        if raw_token is None:
            return None
        validated_token = self.get_validated_token(raw_token)
        return self.get_user(validated_token), validated_token
