from django.contrib import admin
from .models import Notification, WebhookSubscription

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'emisor', 'titulo', 'tipo', 'leida', 'created_at')
    list_filter = ('tipo', 'leida', 'created_at')
    search_fields = ('usuario__email', 'emisor__email', 'titulo', 'mensaje')
    readonly_fields = ('created_at', 'updated_at', 'fecha_lectura')
    fieldsets = (
        ('General', {
            'fields': ('uid', 'titulo', 'mensaje', 'tipo')
        }),
        ('Destinatario y Emisor', {
            'fields': ('usuario', 'emisor')
        }),
        ('Estado', {
            'fields': ('leida', 'fecha_lectura')
        }),
        ('Metadatos', {
            'fields': ('enlace', 'objeto_relacionado_tipo', 'objeto_relacionado_id', 'created_at', 'updated_at')
        }),
    )
