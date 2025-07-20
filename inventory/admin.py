from django.contrib import admin
from .models import BoxType, FruitLot, GoodsReception, Product, Supplier, ReceptionDetail

admin.site.register(BoxType)
admin.site.register(FruitLot)
admin.site.register(Product)
admin.site.register(GoodsReception)
admin.site.register(Supplier)
admin.site.register(ReceptionDetail)
