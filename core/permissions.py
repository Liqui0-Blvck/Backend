from rest_framework import permissions

class IsSameBusiness(permissions.BasePermission):
    """
    Permite acceso solo si el usuario pertenece al mismo business que el recurso.
    """
    def has_object_permission(self, request, view, obj):
        # Obtener el perfil del usuario
        perfil = getattr(request.user, 'perfil', None)
        if perfil is None:
            return False

        # Determinar el business del usuario. Para Proveedor, usar el business del Supplier asociado
        user_business = getattr(perfil, 'business', None)
        if (user_business is None) and request.user.groups.filter(name='Proveedor').exists():
            proveedor = getattr(perfil, 'proveedor', None)
            user_business = getattr(proveedor, 'business', None)
        if user_business is None:
            return False
        
        # Para modelos con campo business
        if hasattr(obj, 'business'):
            return obj.business == user_business
        # Para modelos relacionados
        if hasattr(obj, 'user') and hasattr(obj.user, 'perfil'):
            return obj.user.perfil.business == user_business
        return False

    def has_permission(self, request, view):
        # Verificar que el usuario tenga un perfil con negocio
        perfil = getattr(request.user, 'perfil', None)
        if perfil is None:
            return False
        if perfil.business is not None:
            return True
        # Permitir para Proveedor si su Supplier define business
        if request.user.groups.filter(name='Proveedor').exists():
            proveedor = getattr(perfil, 'proveedor', None)
            return proveedor is not None and getattr(proveedor, 'business', None) is not None
        return False


class IsProveedorReadOnly(permissions.BasePermission):
    """
    Permite solo métodos de lectura (SAFE_METHODS) a usuarios del grupo 'Proveedor'.
    Para otros usuarios, no aplica ninguna restricción adicional.
    """
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        # Si es Proveedor, solo lectura; si no, permitir y que otras permissions decidan
        if user.groups.filter(name='Proveedor').exists():
            return request.method in permissions.SAFE_METHODS
        return True

    def has_object_permission(self, request, view, obj):
        # Consistente con has_permission
        return self.has_permission(request, view)


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

