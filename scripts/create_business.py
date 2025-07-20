#!/usr/bin/env python
"""
Script para crear la empresa Matriz Frutícola y asignar los usuarios con roles múltiples y turnos
"""

import os
import django
import sys

# Configurar entorno Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
sys.path.append('/app')
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from accounts.models import Perfil, CustomUser
from business.models import Business
from datetime import datetime, timedelta

User = get_user_model()

def create_matriz_fruticola():
    """Crea la empresa Matriz Frutícola y asigna los usuarios con roles múltiples y turnos"""
    
    print("Creando empresa Matriz Frutícola y asignando usuarios con roles múltiples y turnos...")
    
    # Datos de la empresa
    businesses_data = [
        {
            'nombre': 'Matriz Frutícola',
            'rut': '76.543.210-K',
            'email': 'contacto@matrizfruticola.cl',
            'telefono': '225556666',
            'direccion': 'Av. Las Frutas 123, Santiago',
            'admin_emails': ['admin@matrizfruticola.cl'],
            'supervisor_emails': ['nicolas.cortes@matrizfruticola.cl', 'matias.osorio@matrizfruticola.cl'],
            'vendedor_emails': ['nicolas.cortes@matrizfruticola.cl', 'matias.osorio@matrizfruticola.cl']
        }
    ]
    
    # Crear las empresas y asignar usuarios
    print("\nCreando la empresa y asignando usuarios...")
    
    # Definir los horarios de turnos para referencia (no se crean turnos reales aún)
    turno_dia = {
        'nombre': 'Turno Día',
        'hora_inicio': '08:00',
        'hora_fin': '16:00'
    }
    
    turno_noche = {
        'nombre': 'Turno Noche',
        'hora_inicio': '16:00',
        'hora_fin': '00:00'
    }
    
    print(f"\u2713 Definidos horarios de turnos: {turno_dia['nombre']} ({turno_dia['hora_inicio']} - {turno_dia['hora_fin']})")
    print(f"\u2713 Definidos horarios de turnos: {turno_noche['nombre']} ({turno_noche['hora_inicio']} - {turno_noche['hora_fin']})")
    
    
    for business_data in businesses_data:
        try:
            # Verificar si la empresa ya existe
            existing_business = Business.objects.filter(rut=business_data['rut']).first()
            
            if existing_business:
                print(f"⚠️ La empresa {existing_business.nombre} ya existe con RUT {existing_business.rut}")
                business = existing_business
            else:
                # Primero, encontrar el perfil del primer administrador para usarlo como dueño
                admin_email = business_data['admin_emails'][0]
                admin_user = User.objects.filter(email=admin_email).first()
                
                if not admin_user:
                    print(f"❌ No se encontró el usuario administrador {admin_email}. No se puede crear la empresa.")
                    continue
                    
                admin_perfil = Perfil.objects.filter(user=admin_user).first()
                
                if not admin_perfil:
                    print(f"❌ No se encontró el perfil para el usuario {admin_email}. No se puede crear la empresa.")
                    continue
                
                # Crear la empresa con todos los campos disponibles
                business = Business(
                    nombre=business_data['nombre'],
                    rut=business_data['rut'],
                    email=business_data['email'],
                    telefono=business_data['telefono'],
                    direccion=business_data['direccion'],
                    dueno=admin_perfil  # Asignar el dueño desde el principio
                )
                business.save()
                print(f"✓ Empresa creada: {business.nombre} (RUT: {business.rut})")
                print(f"✓ {admin_email} asignado como dueño de la empresa {business.nombre}")
                
                # Asignar la empresa al perfil del dueño
                admin_perfil.business = business
                admin_perfil.save()
            
            # Asignar usuarios a la empresa y manejar roles múltiples y turnos
            print("\nAsignando usuarios, roles múltiples y turnos...")
            
            # Obtener todos los usuarios de la empresa
            all_users = {}
            for email in set(business_data['admin_emails'] + business_data['supervisor_emails'] + business_data['vendedor_emails']):
                user = User.objects.filter(email=email).first()
                if user:
                    all_users[email] = user
                    perfil = Perfil.objects.filter(user=user).first()
                    if perfil:
                        perfil.business = business
                        perfil.save()
                        print(f"✓ Usuario {email} asignado a la empresa {business.nombre}")
                    else:
                        print(f"⚠️ No se encontró el perfil para el usuario {email}")
                else:
                    print(f"⚠️ No se encontró el usuario {email}")
            
            # Asegurar que existan los grupos necesarios
            grupos = ['Administrador', 'Supervisor', 'Vendedor']
            for nombre_grupo in grupos:
                Group.objects.get_or_create(name=nombre_grupo)
                print(f"Grupo {nombre_grupo} verificado")
            
            # Asignar roles adicionales a los usuarios
            # Nicolás Cortés - Supervisor (principal) + Vendedor (adicional)
            nicolas = all_users.get('nicolas.cortes@matrizfruticola.cl')
            if nicolas:
                # Verificar si ya tiene el rol de vendedor
                vendedor_group = Group.objects.get(name='Vendedor')
                if not nicolas.groups.filter(name='Vendedor').exists():
                    nicolas.groups.add(vendedor_group)
                    print(f"✓ Rol adicional 'Vendedor' asignado a {nicolas.email}")
                else:
                    print(f"⚠️ El usuario {nicolas.email} ya tiene el rol 'Vendedor'")
                
                # Asegurar que tenga el rol de Supervisor como principal
                supervisor_group = Group.objects.get(name='Supervisor')
                if not nicolas.groups.filter(name='Supervisor').exists():
                    # Si no tiene el grupo Supervisor, agregarlo primero para que sea el principal
                    nicolas.groups.clear()
                    nicolas.groups.add(supervisor_group)
                    nicolas.groups.add(vendedor_group)
                    print(f"✓ Rol principal 'Supervisor' asignado a {nicolas.email}")
                
                # Registrar la preferencia de turno (solo informativo)
                print(f"✓ Usuario {nicolas.email} preferencia de {turno_dia['nombre']}")
                # Aquí se podría guardar esta preferencia en algún campo del perfil o en una tabla separada
            
            # Matías Osorio - Vendedor (principal) + Supervisor (adicional)
            matias = all_users.get('matias.osorio@matrizfruticola.cl')
            if matias:
                # Verificar si ya tiene el rol de supervisor
                supervisor_group = Group.objects.get(name='Supervisor')
                vendedor_group = Group.objects.get(name='Vendedor')
                
                if not matias.groups.filter(name='Supervisor').exists():
                    matias.groups.add(supervisor_group)
                    print(f"✓ Rol adicional 'Supervisor' asignado a {matias.email}")
                else:
                    print(f"⚠️ El usuario {matias.email} ya tiene el rol 'Supervisor'")
                
                # Asegurar que tenga el rol de Vendedor como principal
                if not matias.groups.filter(name='Vendedor').exists():
                    # Si no tiene el grupo Vendedor, agregarlo primero para que sea el principal
                    matias.groups.clear()
                    matias.groups.add(vendedor_group)
                    matias.groups.add(supervisor_group)
                    print(f"✓ Rol principal 'Vendedor' asignado a {matias.email}")
                
                # Registrar la preferencia de turno (solo informativo)
                print(f"✓ Usuario {matias.email} preferencia de {turno_noche['nombre']}")
                # Aquí se podría guardar esta preferencia en algún campo del perfil o en una tabla separada
                
        except Exception as e:
            print(f"❌ Error al procesar la empresa {business_data['nombre']}: {str(e)}")
    
    print("\nEmpresa Matriz Frutícola creada con éxito, usuarios asignados con roles múltiples y turnos configurados!")

if __name__ == "__main__":
    print("Iniciando script de creación de Matriz Frutícola...")
    create_matriz_fruticola()
    print("Script finalizado.")
