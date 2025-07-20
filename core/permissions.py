from rest_framework import permissions

class IsSameBusiness(permissions.BasePermission):
    """
    Permite acceso solo si el usuario pertenece al mismo business que el recurso.
    """
    def has_object_permission(self, request, view, obj):
        # Obtener el perfil del usuario
        perfil = getattr(request.user, 'perfil', None)
        if perfil is None or perfil.business is None:
            return False
            
        # Para modelos con campo business
        if hasattr(obj, 'business'):
            return obj.business == perfil.business
        # Para modelos relacionados
        if hasattr(obj, 'user') and hasattr(obj.user, 'perfil'):
            return obj.user.perfil.business == perfil.business
        return False

    def has_permission(self, request, view):
        # Verificar que el usuario tenga un perfil con negocio
        perfil = getattr(request.user, 'perfil', None)
        return perfil is not None and perfil.business is not None


class IsAdminOrOwner(permissions.BasePermission):
    """
    Permite acceso solo a usuarios con rol de Administrador (dueño del negocio).
    """
    def has_permission(self, request, view):
        user = request.user
        return (
            user and user.is_authenticated and
            user.groups.filter(name='Administrador').exists()
        )
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)

class IsSupervisor(permissions.BasePermission):
    """
    Permite acceso solo a usuarios con rol de Supervisor.
    """
    def has_permission(self, request, view):
        user = request.user
        return (
            user and user.is_authenticated and
            user.groups.filter(name='Supervisor').exists()
        )
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)

