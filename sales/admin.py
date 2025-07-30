from django.contrib import admin
from .models import Sale, SalePending, Customer, CustomerPayment

admin.site.register(Sale)

admin.site.register(SalePending)

admin.site.register(Customer)

admin.site.register(CustomerPayment)

