from django.contrib import admin
from .models import BoxType, FruitLot, GoodsReception, Product, Supplier, ReceptionDetail, FruitBin
from .bin_to_lot_models import BinToLotTransformation, BinToLotTransformationDetail

@admin.register(BoxType)
class BoxTypeAdmin(admin.ModelAdmin):
    list_display = ("nombre", "business", "peso_caja", "capacidad_por_caja", "stock_cajas_vacias")
    list_filter = ("business",)
    search_fields = ("nombre",)

@admin.register(FruitBin)
class FruitBinAdmin(admin.ModelAdmin):
    list_display = ("codigo", "producto", "business", "estado", "ubicacion", "peso_bruto", "peso_tara")
    list_filter = ("business", "estado", "ubicacion")
    search_fields = ("codigo", "producto__nombre")

admin.site.register(FruitLot)
admin.site.register(Product)
admin.site.register(GoodsReception)
admin.site.register(Supplier)
admin.site.register(ReceptionDetail)
admin.site.register(BinToLotTransformation)
admin.site.register(BinToLotTransformationDetail)
