from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from .models import CustomUser, Perfil

class PerfilInline(admin.StackedInline):
    model = Perfil
    can_delete = False
    verbose_name_plural = 'Perfil'
    fk_name = 'user'
    fields = ('rut', 'phone', 'business', 'proveedor')

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('email', 'get_full_name', 'get_roles_display', 'is_active', 'is_staff')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'groups')
    search_fields = ('email', 'first_name', 'last_name', 'groups__name')
    ordering = ('email',)
    inlines = (PerfilInline,)
    filter_horizontal = ('groups', 'user_permissions',)
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'second_name', 'last_name', 'second_last_name')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'first_name', 'last_name', 'is_active', 'is_staff')}),
    )
    
    def get_roles_display(self, obj):
        return ", ".join(obj.groups.values_list('name', flat=True)) if obj.groups.exists() else "-"
    get_roles_display.short_description = 'Roles'
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"
    get_full_name.short_description = 'Nombre completo'

class PerfilAdmin(admin.ModelAdmin):
    list_display = ('user', 'rut', 'phone', 'business', 'proveedor')
    search_fields = ('user__email', 'rut', 'phone', 'proveedor__nombre', 'proveedor__rut')
    list_filter = ('business', 'proveedor')

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Perfil, PerfilAdmin)
