#!/usr/bin/env python
"""
Script para crear perfiles para usuarios existentes en FruitPOS
"""

import os
import django
import sys

# Configurar entorno Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# Agregar el directorio actual al path para que Django pueda encontrar los módulos
sys.path.append('/app')

django.setup()

from django.contrib.auth import get_user_model
from accounts.models import Perfil
from business.models import Business
from scripts.accounts_seed import users_data

User = get_user_model()

def create_profiles():
    """Crea perfiles para usuarios existentes según los datos de semilla"""
    
    print("Creando perfiles para usuarios existentes...")
    
    # Buscar o crear el usuario admin si no existe
    admin_email = 'admin@matrizfruticola.cl'
    try:
        admin_user = User.objects.get(email=admin_email)
        print(f"Usuario administrador encontrado: {admin_email}")
    except User.DoesNotExist:
        print(f"⚠️ Usuario administrador {admin_email} no encontrado. Creándolo...")
        admin_user = User.objects.create_user(
            email=admin_email,
            password='admin123',
            is_staff=True,
            is_superuser=True
        )
        print(f"✓ Usuario administrador {admin_email} creado.")
    
    # Verificar si el admin ya tiene perfil
    try:
        admin_perfil = admin_user.perfil
        print(f"El usuario administrador ya tiene perfil.")
    except Perfil.DoesNotExist:
        print(f"⚠️ El usuario administrador no tiene perfil. Creando uno temporal...")
        # Generar un RUT válido y corto para el admin
        rut_admin = f'RUT-ADMIN'
        admin_perfil = Perfil.objects.create(
            user=admin_user,
            rut=rut_admin
        )
        print(f"✓ Perfil temporal creado para el administrador.")
    
    # Obtener el negocio principal (Matriz Frutícola)
    try:
        business = Business.objects.get(nombre='Matriz Frutícola')
        print(f"Trabajando con el negocio: '{business.nombre}'")
    except Business.DoesNotExist:
        print("⚠️ El negocio 'Matriz Frutícola' no existe. Creándolo...")
        # Crear el negocio si no existe
        business = Business.objects.create(
            nombre='Matriz Frutícola',
            email='contacto@matrizfruticola.cl',
            telefono='225556666',
            direccion='Av. Las Frutas 123, Santiago',
            dueno=admin_perfil  # Asignar el perfil del admin como dueño
        )
        print(f"✓ Negocio '{business.nombre}' creado con dueño {admin_email}.")
        
        # Actualizar el perfil del admin con el negocio
        admin_perfil.business = business
        admin_perfil.save()
        print(f"✓ Perfil del administrador actualizado con el negocio.")
    
    
    # Crear perfiles para usuarios existentes
    for email, user_data in users_data.items():
        try:
            user = User.objects.get(email=email)
            
            # Verificar si ya tiene perfil
            try:
                perfil = user.perfil
                print(f"⚠️ Usuario {email} ya tiene perfil, actualizando datos...")
                
                # Actualizar datos del perfil
                perfil_data = user_data.get('perfil', {})
                perfil.rut = perfil_data.get('rut', f'RUT-{email}')
                perfil.phone = perfil_data.get('phone', '')
                perfil.business = business
                perfil.save()
                print(f"✓ Perfil de {email} actualizado.")
                
            except Perfil.DoesNotExist:
                # Crear nuevo perfil
                perfil_data = user_data.get('perfil', {})
                perfil = Perfil.objects.create(
                    user=user,
                    rut=perfil_data.get('rut', f'RUT-{email}'),
                    phone=perfil_data.get('phone', ''),
                    business=business
                )
                print(f"✓ Perfil creado para {email}.")
                
        except User.DoesNotExist:
            print(f"⚠️ Usuario {email} no encontrado, saltando...")
    
    # Verificar usuarios sin perfil en accounts_seed.py
    for user in User.objects.all():
        if user.email not in users_data:
            try:
                perfil = user.perfil
                print(f"⚠️ Usuario {user.email} no está en datos de semilla pero tiene perfil.")
            except Perfil.DoesNotExist:
                print(f"⚠️ Usuario {user.email} no está en datos de semilla y no tiene perfil. Creando perfil genérico...")
                # Generar un RUT válido y corto (máximo 15 caracteres)
                username = user.email.split('@')[0]
                rut_generico = f'RUT-{username[:8]}'
                perfil = Perfil.objects.create(
                    user=user,
                    rut=rut_generico,
                    business=business
                )
                print(f"✓ Perfil genérico creado para {user.email}.")
    
    print("\nCreación de perfiles completada con éxito!")

if __name__ == "__main__":
    create_profiles()
