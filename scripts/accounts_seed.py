#!/usr/bin/env python
"""
Script para crear usuarios y perfiles para Matriz Frutícola
Utiliza el sistema de grupos de Django para manejar roles
"""

import os
import sys
import django

# Configurar entorno Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from accounts.models import Perfil
from business.models import Business

User = get_user_model()

# Datos de usuarios para Matriz Frutícola
users_data = {
    # Admin principal
    'admin@matrizfruticola.cl': {
        'password': 'admin123',
        'first_name': 'Admin',
        'last_name': 'Principal',
        'roles': ['Administrador'],
        'perfil': {
            'rut': '11.111.111-1',
            'phone': '912345678',
        },
        'business_data': {
            'nombre': 'Matriz Frutícola',
            'email': 'contacto@matrizfruticola.cl',
            'telefono': '225556666',
            'direccion': 'Av. Las Frutas 123, Santiago',
        }
    },
    # Nicolás Cortés - Supervisor y Vendedor (Turno Día)
    'nicolas.cortes@matrizfruticola.cl': {
        'password': 'nicolas123',
        'first_name': 'Nicolás',
        'last_name': 'Cortés',
        'roles': ['Supervisor', 'Vendedor'],
        'perfil': {
            'rut': '12.345.678-9',
            'phone': '987654321',
        },
        'preferencia_turno': 'dia'
    },
    # Matías Osorio - Vendedor y Supervisor (Turno Noche)
    'matias.osorio@matrizfruticola.cl': {
        'password': 'matias123',
        'first_name': 'Matías',
        'last_name': 'Osorio',
        'roles': ['Vendedor', 'Supervisor'],
        'perfil': {
            'rut': '98.765.432-1',
            'phone': '912345678',
        },
        'preferencia_turno': 'noche'
    },
}

def create_users():
    # Asegurar que existan los grupos necesarios
    grupos = ['Administrador', 'Supervisor', 'Vendedor']
    for nombre_grupo in grupos:
        Group.objects.get_or_create(name=nombre_grupo)
        print(f"Grupo '{nombre_grupo}' verificado.")

    # Obtener el negocio una sola vez
    try:
        business = Business.objects.get(nombre='Matriz Frutícola')
        print(f"Trabajando con el negocio: '{business.nombre}'")
    except Business.DoesNotExist:
        print("Error: La empresa 'Matriz Frutícola' no existe. Ejecuta primero el script para crear negocios.")
        return

    # Crear o actualizar usuarios y perfiles
    for email, data in users_data.items():
        # Crear o encontrar el usuario
        user, user_created = User.objects.update_or_create(
            email=email,
            defaults={
                'first_name': data['first_name'],
                'last_name': data['last_name']
            }
        )
        if user_created:
            user.set_password(data['password'])
            user.save()
            print(f"Usuario '{email}' creado con éxito.")
        else:
            print(f"Usuario '{email}' ya existía, actualizando datos.")

        # Asignar roles (grupos)
        user.groups.clear()
        for rol in data['roles']:
            grupo = Group.objects.get(name=rol)
            user.groups.add(grupo)
        print(f"  - Roles asignados: {', '.join(data['roles'])}")

        # Crear o actualizar perfil, asignando el negocio directamente
        perfil_data = data.get('perfil', {})
        perfil, perfil_created = Perfil.objects.update_or_create(
            user=user,
            defaults={
                'rut': perfil_data.get('rut'),
                'phone': perfil_data.get('phone'),
                'business': business  # Asignar el negocio aquí
            }
        )
        if perfil_created:
            print(f"  - Perfil creado y asignado al negocio '{business.nombre}'.")
        else:
            print(f"  - Perfil actualizado y asignado al negocio '{business.nombre}'.")

        # Mostrar preferencia de turno (solo informativo)
        if 'preferencia_turno' in data:
            print(f"  - Preferencia de turno: {data['preferencia_turno']}")

if __name__ == "__main__":
    create_users()
    print("\nScript completado con éxito!")
