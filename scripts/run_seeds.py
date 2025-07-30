#!/usr/bin/env python
"""
Script para ejecutar las semillas y crear datos iniciales en FruitPOS
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
from business.models import Business
from scripts.accounts_seed import users_data as accounts_seed_data

User = get_user_model()

def run_seeds():
    """Ejecuta las semillas para crear datos iniciales"""
    
    print("Creando usuarios iniciales desde los datos de semilla...")
    
    # Diccionario para almacenar los negocios creados (por RUT)
    businesses = {}
    
    # Crear usuarios desde los datos de semilla
    for email, user_data in accounts_seed_data.items():
        # Obtener datos del negocio
        business_data = user_data.get('business', {})
        business_name = business_data.get('nombre')
        business_rut = business_data.get('rut')
        
        # Manejar roles múltiples
        roles_str = user_data.get('roles', [])
        if isinstance(roles_str, str):
            roles = [r.strip() for r in roles_str.split(',') if r.strip()]
        elif isinstance(roles_str, list):
            roles = roles_str
        else:
            roles = []
            
        primary_role = roles[0] if roles else ''  # El primer rol será el principal
        
        # Crear grupos si no existen
        for role in roles:
            if role:
                Group.objects.get_or_create(name=role)
        
        # Verificar si el usuario ya existe
        if User.objects.filter(email=email).exists():
            print(f"⚠️ Usuario {email} ya existe, saltando...")
            continue
        
        # Crear el usuario con el rol principal
        try:
            user = User.objects.create_user(
                email=email,
                password=user_data.get('password'),
                first_name=user_data.get('first_name', ''),
                last_name=user_data.get('last_name', ''),
                is_staff=primary_role.lower() == 'admin',
                is_superuser=primary_role.lower() == 'admin'
                # No asignar role como campo ya que no existe en el modelo
            )
            
            # Asignar grupos (roles) al usuario
            for role in roles:
                if role:
                    try:
                        group = Group.objects.get(name=role)
                        user.groups.add(group)
                        print(f"  - Rol '{role}' asignado a {user.email}")
                    except Group.DoesNotExist:
                        print(f"  ⚠️ El rol '{role}' no existe y no pudo ser asignado a {user.email}")
            
            # Crear el perfil del usuario
            perfil_data = user_data.get('perfil', {})
            perfil = Perfil.objects.create(
                user=user,
                rut=perfil_data.get('rut', f'RUT-{email}'),  # Usar email como parte del RUT si no hay uno definido
                phone=perfil_data.get('phone', '')  # Nota: en el modelo es 'phone', no 'telefono'
            )
            
            # Si el usuario tiene múltiples roles, informar al usuario
            if len(roles) > 1:
                roles_str = ', '.join(roles)
                print(f"✓ Usuario {user.email} tiene múltiples roles: {roles_str}")
                print(f"  Nota: Se ha asignado '{primary_role}' como rol principal en el sistema.")
                print(f"  Los roles adicionales deberán ser gestionados manualmente en la aplicación.")
            
            print(f"✓ Usuario creado: {user.email} (Rol: {user_data.get('role')})")
        except Exception as e:
            print(f"❌ Error al crear usuario {email}: {str(e)}")
    
    print("\nUsuarios creados con éxito!")
    print("Puede acceder al sistema con las credenciales proporcionadas en los datos de semilla.")

if __name__ == "__main__":
    run_seeds()
