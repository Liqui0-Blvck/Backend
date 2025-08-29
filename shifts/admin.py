from django.contrib import admin
from .models import Shift, ShiftClosing

admin.site.register(Shift)


@admin.register(ShiftClosing)
class ShiftClosingAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'shift',
        'business',
        'fecha_cierre_caja',
        'cerrado_por',
    )
    list_filter = ('business', 'fecha_cierre_caja')
    search_fields = (
        'shift__uid',
        'cerrado_por__username',
        'cerrado_por__first_name',
        'cerrado_por__last_name',
    )
    date_hierarchy = 'fecha_cierre_caja'
