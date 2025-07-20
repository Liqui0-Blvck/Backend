#!/usr/bin/env python
# Seed para crear turnos de día y noche en el sistema FruitPOS

import os
import sys
import django
from datetime import datetime, timedelta, time
from django.utils import timezone

# Configurar entorno Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

# Importar modelos necesarios
from shifts.models import Shift
from business.models import Business
from accounts.models import CustomUser, Perfil

def create_shifts_seed():
    """
    Crea turnos de día (06:00-14:00) y noche (20:00-06:00) para las empresas registradas
    """
    print("🕒 Creando turnos de día y noche...")
    
    # Fecha actual (Django ya usa UTC por defecto)
    now = timezone.now()
    # Convertir a fecha local sin zona horaria específica
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Definir horarios de turnos
    turno_dia_inicio = today.replace(hour=6, minute=0)
    turno_dia_fin = today.replace(hour=14, minute=0)
    
    turno_noche_inicio = today.replace(hour=20, minute=0)
    turno_noche_fin = (today + timedelta(days=1)).replace(hour=6, minute=0)
    
    # Obtener todas las empresas
    businesses = Business.objects.all()
    
    for business in businesses:
        print(f"\n✓ Creando turnos para empresa: {business.nombre}")
        
        # Buscar usuarios supervisores y vendedores para esta empresa
        perfiles = Perfil.objects.filter(business=business)
        supervisor_users = [perfil.user for perfil in perfiles if perfil.user.groups.filter(name='Supervisor').exists()]
        vendedor_users = [perfil.user for perfil in perfiles if perfil.user.groups.filter(name='Vendedor').exists()]
        
        if not supervisor_users and not vendedor_users:
            print(f"⚠️ No se encontraron supervisores ni vendedores para {business.nombre}, saltando...")
            continue
        
        # Asignar supervisor para turno de día (si hay) o vendedor
        turno_dia_user = supervisor_users[0] if supervisor_users else vendedor_users[0]
        rol_dia = 'Supervisor' if turno_dia_user in supervisor_users else 'Vendedor'
        print(f"✓ Usuario para turno de día: {turno_dia_user.email} (rol: {rol_dia})")
        
        # Asignar vendedor para turno de noche (si hay) o supervisor
        turno_noche_user = vendedor_users[0] if vendedor_users else supervisor_users[0]
        if len(vendedor_users) > 1:
            turno_noche_user = vendedor_users[1]  # Usar otro vendedor si hay más de uno
        rol_noche = 'Vendedor' if turno_noche_user in vendedor_users else 'Supervisor'
        print(f"✓ Usuario para turno de noche: {turno_noche_user.email} (rol: {rol_noche})")
        
        # Crear turno de día (cerrado)
        turno_dia, created = Shift.objects.get_or_create(
            business=business,
            fecha_apertura=turno_dia_inicio,
            defaults={
                'usuario_abre': turno_dia_user,
                'usuario_cierra': turno_dia_user,
                'fecha_cierre': turno_dia_fin,
                'estado': 'cerrado',
                'motivo_diferencia': 'Turno de día (06:00-14:00) creado por seed script'
            }
        )
        
        if created:
            print(f"✓ Turno de día creado: {turno_dia_inicio.strftime('%H:%M')} - {turno_dia_fin.strftime('%H:%M')}")
        else:
            print(f"ℹ️ Ya existe un turno de día para {business.nombre} en esta fecha")
        
        # Crear turno de noche (abierto)
        turno_noche, created = Shift.objects.get_or_create(
            business=business,
            fecha_apertura=turno_noche_inicio,
            defaults={
                'usuario_abre': turno_noche_user,
                'estado': 'abierto',
                'motivo_diferencia': 'Turno de noche (20:00-06:00) creado por seed script'
            }
        )
        
        if created:
            print(f"✓ Turno de noche creado: {turno_noche_inicio.strftime('%H:%M')} - {turno_noche_fin.strftime('%H:%M')} (abierto)")
        else:
            print(f"ℹ️ Ya existe un turno de noche para {business.nombre} en esta fecha")

if __name__ == "__main__":
    create_shifts_seed()
    print("\n✅ Seed de turnos completado con éxito!")
