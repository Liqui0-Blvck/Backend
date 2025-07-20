from rest_framework.routers import DefaultRouter
from .views import ConfiguracionUsuarioViewSet, CustomUserViewSet, LoginView, RefreshView, MeView, LogoutView, get_csrf_token, ChangePasswordView
from django.urls import path, include

# Router para endpoints de usuarios bajo /accounts/users/
accounts_router = DefaultRouter()
accounts_router.register(r'users', CustomUserViewSet, basename='user')

# Router principal para mantener compatibilidad con código existente
router = DefaultRouter()
router.register(r'users', CustomUserViewSet, basename='user')

urlpatterns = [
    # Endpoints de autenticación
    path('login/', LoginView.as_view(), name='login'),
    path('refresh/', RefreshView.as_view(), name='refresh'),
    path('me/', MeView.as_view(), name='me'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('csrf/', get_csrf_token, name='get_csrf_token'),
    path('config/', ConfiguracionUsuarioViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update'}), name='configuracion'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),

] + router.urls  # Mantener los endpoints originales para compatibilidad
