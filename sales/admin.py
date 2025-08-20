from django.contrib import admin
from .models import Sale, SalePending, Customer, CustomerPayment
from .models_billing import BillingInfo

# Configuración avanzada para modelos de ventas
class SaleAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'business', 'total', 'created_at', 'metodo_pago', 'estado_pago')
    list_filter = ('metodo_pago', 'estado_pago', 'created_at', 'business')
    search_fields = ('cliente__nombre', 'cliente__rut', 'id', 'codigo_venta')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'updated_at', 'codigo_venta')
    raw_id_fields = ('cliente',)
    
    fieldsets = (
        ('Información General', {
            'fields': ('cliente', 'business', 'codigo_venta', 'created_at')
        }),
        ('Detalles de Venta', {
            'fields': ('total', 'metodo_pago', 'estado_pago', 'comprobante')
        }),
        ('Información de Crédito', {
            'fields': ('pagado', 'saldo_pendiente', 'fecha_vencimiento'),
            'classes': ('collapse',)
        }),
        ('Estado de Cancelación', {
            'fields': ('cancelada', 'fecha_cancelacion', 'motivo_cancelacion'),
            'classes': ('collapse',)
        }),
    )

class SalePendingAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'business', 'total', 'created_at', 'estado')
    list_filter = ('estado', 'created_at', 'business')
    search_fields = ('cliente__nombre', 'cliente__rut', 'id', 'codigo_venta')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('cliente',)
    
    fieldsets = (
        ('Información General', {
            'fields': ('cliente', 'business', 'codigo_venta')
        }),
        ('Detalles', {
            'fields': ('total', 'estado', 'metodo_pago')
        }),
        ('Datos del Cliente', {
            'fields': ('nombre_cliente', 'rut_cliente', 'telefono_cliente', 'email_cliente'),
            'classes': ('collapse',)
        }),
        ('Información Adicional', {
            'fields': ('comentarios', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

# Registro de modelos con configuración avanzada
admin.site.register(Sale, SaleAdmin)
admin.site.register(SalePending, SalePendingAdmin)

# Registro de Customer con BillingInfo como inline
class BillingInfoInline(admin.StackedInline):
    model = BillingInfo
    extra = 0
    fieldsets = (
        ('Datos Fiscales', {
            'fields': ('razon_social', 'rut_facturacion', 'giro')
        }),
        ('Dirección de Facturación', {
            'fields': ('direccion_facturacion', 'comuna', 'ciudad', 'region')
        }),
        ('Contacto', {
            'fields': ('email_facturacion', 'telefono_facturacion')
        }),
        ('Preferencias', {
            'fields': ('tipo_documento_preferido', 'condiciones_pago', 'notas')
        }),
    )
    classes = ['collapse-open']
    can_delete = False
    verbose_name_plural = 'Información de Facturación'

class CustomerAdmin(admin.ModelAdmin):
    inlines = [BillingInfoInline]
    list_display = ('nombre', 'rut', 'telefono', 'email', 'credito_activo', 'saldo_actual', 'tiene_billing_info', 'business')
    list_filter = ('frecuente', 'credito_activo', 'business')
    search_fields = ('nombre', 'rut', 'telefono', 'email')
    list_editable = ('credito_activo',)
    actions = ['activar_credito', 'desactivar_credito', 'marcar_como_frecuente', 'desmarcar_como_frecuente']
    fieldsets = (
        ('Información Personal', {
            'fields': ('nombre', 'rut', 'telefono', 'email')
        }),
        ('Configuración de Negocio', {
            'fields': ('business', 'frecuente')
        }),
        ('Configuración de Crédito', {
            'fields': ('credito_activo', 'limite_credito')
        }),
    )
    
    def tiene_billing_info(self, obj):
        return hasattr(obj, 'billing_info')
    tiene_billing_info.boolean = True
    tiene_billing_info.short_description = 'Info. Facturación'
    
    def activar_credito(self, request, queryset):
        queryset.update(credito_activo=True)
        self.message_user(request, f'{queryset.count()} clientes han sido actualizados con crédito activo.')
    activar_credito.short_description = 'Activar crédito para los clientes seleccionados'
    
    def desactivar_credito(self, request, queryset):
        queryset.update(credito_activo=False)
        self.message_user(request, f'{queryset.count()} clientes han sido actualizados con crédito desactivado.')
    desactivar_credito.short_description = 'Desactivar crédito para los clientes seleccionados'
    
    def marcar_como_frecuente(self, request, queryset):
        queryset.update(frecuente=True)
        self.message_user(request, f'{queryset.count()} clientes han sido marcados como frecuentes.')
    marcar_como_frecuente.short_description = 'Marcar como clientes frecuentes'
    
    def desmarcar_como_frecuente(self, request, queryset):
        queryset.update(frecuente=False)
        self.message_user(request, f'{queryset.count()} clientes han sido desmarcados como frecuentes.')
    desmarcar_como_frecuente.short_description = 'Desmarcar como clientes frecuentes'

admin.site.register(Customer, CustomerAdmin)
class CustomerPaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'monto', 'fecha_pago', 'metodo_pago', 'get_business')
    list_filter = ('metodo_pago', 'fecha_pago', 'cliente__business')
    search_fields = ('cliente__nombre', 'cliente__rut', 'id', 'notas')
    date_hierarchy = 'fecha_pago'
    raw_id_fields = ('cliente',)
    
    fieldsets = (
        ('Información General', {
            'fields': ('cliente', 'monto', 'fecha_pago')
        }),
        ('Detalles de Pago', {
            'fields': ('metodo_pago', 'comprobante')
        }),
        ('Información Adicional', {
            'fields': ('notas', 'referencia'),
            'classes': ('collapse',)
        }),
    )
    
    def get_business(self, obj):
        return obj.cliente.business if obj.cliente else None
    get_business.short_description = 'Negocio'
    get_business.admin_order_field = 'cliente__business'

admin.site.register(CustomerPayment, CustomerPaymentAdmin)

# Registro independiente de BillingInfo con configuración avanzada
class BillingInfoAdmin(admin.ModelAdmin):
    list_display = ('razon_social', 'rut_facturacion', 'giro', 'cliente', 'tipo_documento_preferido', 'get_business')
    list_filter = ('tipo_documento_preferido', 'region', 'ciudad', 'cliente__business')
    search_fields = ('razon_social', 'rut_facturacion', 'cliente__nombre', 'cliente__rut')
    raw_id_fields = ('cliente',)
    actions = ['copiar_datos_cliente']
    
    fieldsets = (
        ('Cliente', {
            'fields': ('cliente',)
        }),
        ('Datos Fiscales', {
            'fields': ('razon_social', 'rut_facturacion', 'giro')
        }),
        ('Dirección de Facturación', {
            'fields': ('direccion_facturacion', 'comuna', 'ciudad', 'region')
        }),
        ('Contacto', {
            'fields': ('email_facturacion', 'telefono_facturacion')
        }),
        ('Preferencias', {
            'fields': ('tipo_documento_preferido', 'condiciones_pago', 'notas')
        }),
    )
    
    def get_business(self, obj):
        return obj.cliente.business if obj.cliente else None
    get_business.short_description = 'Negocio'
    get_business.admin_order_field = 'cliente__business'
    
    def copiar_datos_cliente(self, request, queryset):
        count = 0
        for billing_info in queryset:
            if billing_info.cliente:
                updated = False
                if not billing_info.razon_social and billing_info.cliente.nombre:
                    billing_info.razon_social = billing_info.cliente.nombre
                    updated = True
                if not billing_info.rut_facturacion and billing_info.cliente.rut:
                    billing_info.rut_facturacion = billing_info.cliente.rut
                    updated = True
                if not billing_info.email_facturacion and billing_info.cliente.email:
                    billing_info.email_facturacion = billing_info.cliente.email
                    updated = True
                if not billing_info.telefono_facturacion and billing_info.cliente.telefono:
                    billing_info.telefono_facturacion = billing_info.cliente.telefono
                    updated = True
                
                if updated:
                    billing_info.save()
                    count += 1
        
        self.message_user(request, f'Se actualizaron {count} registros con datos del cliente.')
    copiar_datos_cliente.short_description = 'Copiar datos desde cliente'

admin.site.register(BillingInfo, BillingInfoAdmin)
