def get_user_role(user):
    """
    Devuelve el rol principal de un usuario basado en los grupos de Django.
    La jerarquía es Administrador > Supervisor > Vendedor.
    """
    if user.groups.filter(name='administrador').exists():
        return 'administrador'
    if user.groups.filter(name='supervisor').exists():
        return 'supervisor'
    if user.groups.filter(name='vendedor').exists():
        return 'vendedor'
    return None
