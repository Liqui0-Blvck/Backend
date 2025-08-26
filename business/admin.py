from django.contrib import admin
from django.utils.safestring import mark_safe
from .models import Business, BusinessConfig
from .models_banking import BankAccount

# Registro de BankAccount como inline para Business
class BankAccountInline(admin.TabularInline):
    model = BankAccount
    extra = 1
    fields = ('banco', 'otro_banco', 'tipo_cuenta', 'numero_cuenta', 'titular', 'activa', 'orden')
    readonly_fields = ('fecha_creacion',)
    show_change_link = True
    classes = ['collapse-open']
    verbose_name = 'Cuenta Bancaria'
    verbose_name_plural = 'Cuentas Bancarias'

# Admin personalizado para Business
class BusinessAdmin(admin.ModelAdmin):
    inlines = [BankAccountInline]
    list_display = ('nombre', 'rut', 'email', 'telefono', 'dueno', 'cuenta_bancaria_count', 'cuentas_activas_count')
    search_fields = ('nombre', 'rut', 'email', 'telefono')
    list_filter = ('created_at',)
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Información General', {
            'fields': ('nombre', 'rut', 'dueno', 'email', 'telefono', 'direccion')
        }),
        ('Información del Sistema', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    # No auto-asignamos 'dueno' aquí; debe ser elegido explícitamente en el formulario del admin.
    
    def cuenta_bancaria_count(self, obj):
        return obj.bank_accounts.count()
    cuenta_bancaria_count.short_description = 'Total Cuentas'
    
    def cuentas_activas_count(self, obj):
        return obj.bank_accounts.filter(activa=True).count()
    cuentas_activas_count.short_description = 'Cuentas Activas'

# Admin para BankAccount independiente
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'business', 'banco_nombre', 'tipo_cuenta', 'titular', 'activa', 'orden', 'fecha_creacion')
    list_filter = ('banco', 'tipo_cuenta', 'activa', 'business')
    search_fields = ('titular', 'numero_cuenta', 'rut_titular', 'email_notificaciones')
    list_editable = ('activa', 'orden')
    readonly_fields = ('fecha_creacion', 'fecha_actualizacion')
    actions = ['activar_cuentas', 'desactivar_cuentas', 'reordenar_cuentas']
    
    fieldsets = (
        ('Información del Banco', {
            'fields': ('business', 'banco', 'otro_banco', 'tipo_cuenta', 'numero_cuenta')
        }),
        ('Información del Titular', {
            'fields': ('titular', 'rut_titular', 'email_notificaciones')
        }),
        ('Configuración', {
            'fields': ('activa', 'orden', 'notas')
        }),
        ('Información del Sistema', {
            'fields': ('fecha_creacion', 'fecha_actualizacion'),
            'classes': ('collapse',)
        }),
    )
    
    def activar_cuentas(self, request, queryset):
        queryset.update(activa=True)
        self.message_user(request, f'{queryset.count()} cuentas bancarias han sido activadas.')
    activar_cuentas.short_description = 'Activar cuentas bancarias seleccionadas'
    
    def desactivar_cuentas(self, request, queryset):
        queryset.update(activa=False)
        self.message_user(request, f'{queryset.count()} cuentas bancarias han sido desactivadas.')
    desactivar_cuentas.short_description = 'Desactivar cuentas bancarias seleccionadas'
    
    def reordenar_cuentas(self, request, queryset):
        # Agrupar por negocio y reordenar cada grupo
        businesses = {}
        for account in queryset:
            if account.business_id not in businesses:
                businesses[account.business_id] = []
            businesses[account.business_id].append(account)
        
        for business_id, accounts in businesses.items():
            for i, account in enumerate(sorted(accounts, key=lambda x: x.orden), 1):
                account.orden = i
                account.save(update_fields=['orden'])
        
        self.message_user(request, f'Se han reordenado las cuentas bancarias de {len(businesses)} negocios.')
    reordenar_cuentas.short_description = 'Reordenar cuentas seleccionadas (por negocio)'

# Registrar modelos en el admin
admin.site.register(Business, BusinessAdmin)
class BusinessConfigAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'default_view_mode', 'updated_at')
    list_filter = ('default_view_mode',)
    search_fields = ('user__nombre', 'user__email')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Usuario', {
            'fields': ('user',)
        }),
        ('Configuración General', {
            'fields': ('default_view_mode',)
        }),
        ('Información del Sistema', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

admin.site.register(BusinessConfig, BusinessConfigAdmin)
admin.site.register(BankAccount, BankAccountAdmin)
