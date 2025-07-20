#!/usr/bin/env python
"""
Script para borrar datos de inventario, ventas y reportes manteniendo usuarios y negocios.
"""
import os
import sys
import django

# Configurar entorno Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.db import transaction
from inventory.models import FruitLot, BoxType, PalletType, MadurationHistory, StockReservation, Product
from sales.models import Sale, SalePending, Customer
from shifts.models import Shift
from django.contrib.auth.models import User
from accounts.models import Perfil, CustomUser
from business.models import Business

def reset_data():
    """Elimina todos los datos excepto usuarios y negocios"""
    print("Iniciando borrado de datos...")
    
    with transaction.atomic():
        # Borrar datos de ventas
        print("Borrando datos de ventas...")
        Sale.objects.all().delete()
        SalePending.objects.all().delete()
        Customer.objects.all().delete()
        
        # Borrar datos de inventario
        print("Borrando datos de inventario...")
        StockReservation.objects.all().delete()
        MadurationHistory.objects.all().delete()
        FruitLot.objects.all().delete()
        BoxType.objects.all().delete()
        PalletType.objects.all().delete()
        Product.objects.all().delete()
        
        # Borrar turnos
        print("Borrando datos de turnos...")
        Shift.objects.all().delete()
        
        print("Datos borrados exitosamente.")
        print("Se mantuvieron usuarios, perfiles y negocios.")
        
        # Mostrar usuarios y negocios existentes
        users = CustomUser.objects.all()
        businesses = Business.objects.all()
        
        print(f"\nUsuarios existentes ({users.count()}):")
        for user in users:
            perfil = getattr(user, 'perfil', None)
            business_name = perfil.business.nombre if perfil and perfil.business else "Sin negocio"
            print(f"- {user.email} - Rol: {user.role} - Negocio: {business_name}")
        
        print(f"\nNegocios existentes ({businesses.count()}):")
        for business in businesses:
            print(f"- {business.nombre} ({business.rut})")
            
        print("\nListo para recrear datos desde cero.")
        print("Ejecute los scripts de seed para generar nuevos datos.")
        print("Por ejemplo: python -m accounts.seed.generate_avocado_data")

if __name__ == "__main__":
    reset_data()
