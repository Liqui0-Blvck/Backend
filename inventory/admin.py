from django.contrib import admin
from .models import BoxType, FruitLot, GoodsReception, Product, Supplier, ReceptionDetail, FruitBin
from .bin_to_lot_models import BinToLotTransformation, BinToLotTransformationDetail

admin.site.register(BoxType)
admin.site.register(FruitLot)
admin.site.register(Product)
admin.site.register(GoodsReception)
admin.site.register(Supplier)
admin.site.register(ReceptionDetail)
admin.site.register(FruitBin)
admin.site.register(BinToLotTransformation)
admin.site.register(BinToLotTransformationDetail)
