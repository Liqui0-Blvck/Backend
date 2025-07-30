#!/usr/bin/env python
"""
Script para asignar grupos a usuarios existentes en FruitPOS
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
from django.contrib.auth.models import Group
from accounts.models import Perfil, CustomUser
from scripts.accounts_seed import users_data

User = get_user_model()

def assign_groups():
    """Asigna grupos a usuarios existentes según los datos de semilla"""
    
    print("Asignando grupos a usuarios existentes...")
    
    # Asegurar que existan los grupos necesarios
    all_roles = set()
    for email, user_data in users_data.items():
        roles_data = user_data.get('roles', [])
        if isinstance(roles_data, list):
            for role in roles_data:
                all_roles.add(role)
        elif isinstance(roles_data, str):
            for role in roles_data.split(','):
                role = role.strip()
                if role:
                    all_roles.add(role)
    
    # Crear los grupos que no existan
    for role in all_roles:
        group, created = Group.objects.get_or_create(name=role)
        if created:
            print(f"✓ Grupo '{role}' creado.")
        else:
            print(f"✓ Grupo '{role}' ya existe.")
    
    # Asignar grupos a usuarios existentes
    for email, user_data in users_data.items():
        try:
            user = User.objects.get(email=email)
            
            # Limpiar grupos existentes
            user.groups.clear()
            
            # Obtener roles
            roles_data = user_data.get('roles', [])
            roles = []
            if isinstance(roles_data, list):
                roles = roles_data
            elif isinstance(roles_data, str):
                roles = [r.strip() for r in roles_data.split(',') if r.strip()]
            
            # Asignar nuevos grupos
            for role in roles:
                if role:
                    try:
                        group = Group.objects.get(name=role)
                        user.groups.add(group)
                        print(f"  - Rol '{role}' asignado a {user.email}")
                    except Group.DoesNotExist:
                        print(f"  ⚠️ El rol '{role}' no existe y no pudo ser asignado a {user.email}")
            
            # Actualizar is_staff e is_superuser según el rol
            is_admin = 'Administrador' in roles or 'admin' in roles
            user.is_staff = is_admin
            user.is_superuser = is_admin
            user.save()
            
            if is_admin:
                print(f"  - Usuario {user.email} configurado como administrador (staff/superuser)")
            
        except User.DoesNotExist:
            print(f"⚠️ Usuario {email} no encontrado, saltando...")
    
    print("\nAsignación de grupos completada con éxito!")

if __name__ == "__main__":
    assign_groups()
