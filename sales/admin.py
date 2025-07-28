from django.contrib import admin
from .models import Sale, SalePending, Customer

admin.site.register(Sale)

admin.site.register(SalePending)

admin.site.register(Customer)
