#!/usr/bin/env python
"""
Script para crear datos de inventario de frutas variadas para Matriz Frutícola
- Crea productos de frutas variadas (manzanas, naranjas, plátanos, etc.)
- Crea proveedores locales
- Crea tipos de cajas y pallets
- Crea recepciones de mercadería con diferentes frutas
- Aprueba las recepciones para generar los lotes automáticamente
"""

import os
import django
import sys
from decimal import Decimal
from datetime import date
import random

# Configurar entorno Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# Agregar el directorio actual al path para que Django pueda encontrar los módulos
sys.path.append('/app')

django.setup()

from django.contrib.auth import get_user_model
from accounts.models import Perfil
from business.models import Business
from inventory.models import (
    Product, BoxType, PalletType, Supplier, GoodsReception, 
    ReceptionDetail, ReceptionImage, FruitLot
)

User = get_user_model()

def create_inventory_seed():
    """Crea datos de inventario para paltas peruanas"""
    
    print("\n🥑 Creando datos de inventario para paltas peruanas...")
    
    # Obtener la empresa Matriz Frutícola (asumimos que ya existe por el script create_business)
    try:
        business = Business.objects.get(nombre='Matriz Frutícola')
        print(f"✓ Empresa encontrada: {business.nombre}")
    except Business.DoesNotExist:
        print("❌ Error: La empresa Matriz Frutícola no existe. Ejecuta primero el script create_business.py")
        return
    
    # Obtener un usuario administrador para la recepción
    try:
        # Buscar usuarios que pertenezcan al grupo Administrador
        from django.contrib.auth.models import Group
        admin_group = Group.objects.get(name='Administrador')
        admin_user = User.objects.filter(
            email__contains='@matrizfruticola.cl',
            groups=admin_group
        ).first()
        
        if not admin_user:
            # Si no hay usuarios en el grupo, buscar cualquier usuario
            admin_user = User.objects.filter(email__contains='@matrizfruticola.cl').first()
            if not admin_user:
                raise User.DoesNotExist
        
        print(f"✓ Usuario administrador encontrado: {admin_user.email}")
    except User.DoesNotExist:
        print("❌ Error: No se encontró ningún usuario para Matriz Frutícola")
        return
    
    # 1. Crear producto de paltas si no existe
    producto, created = Product.objects.get_or_create(
        nombre='Palta Hass',
        marca='Pampa Baja',
        defaults={
            'unidad': 'caja',
            'business': business,
            'activo': True
        }
    )
    if created:
        print(f"✓ Producto creado: {producto.nombre} ({producto.marca})")
    else:
        print(f"ℹ️ Producto ya existe: {producto.nombre} ({producto.marca})")
    
    # 2. Crear o recuperar tipo de caja y pallet
    box_type, created = BoxType.objects.get_or_create(
        nombre="Rejilla",
        business=business,
        defaults={
            'descripcion': "Rejilla estándar para paltas de exportación",
            'peso_caja': Decimal('0.3'),
            'peso_pallet': Decimal('10.0'),
            'business': business
        }
    )
    if created:
        print(f"✓ Tipo de caja creado: {box_type.nombre}")
    else:
        print(f"✓ Tipo de caja existente: {box_type.nombre}")
        
    pallet_type, created = PalletType.objects.get_or_create(
        nombre="Pallet Estándar",
        business=business,
        defaults={
            'descripcion': "Pallet estándar para exportación",
            'peso_pallet': Decimal('25.0'),
            'business': business
        }
    )
    if created:
        print(f"✓ Tipo de pallet creado: {pallet_type.nombre}")
    else:
        print(f"✓ Tipo de pallet existente: {pallet_type.nombre}")
    
    # 4. Crear proveedor peruano si no existe
    proveedor, created = Supplier.objects.get_or_create(
        nombre='Agrícola Pampa Baja S.A.C.',
        defaults={
            'rut': '20411808972',  # RUC peruano
            'direccion': 'Carretera Panamericana Sur Km 5, Arequipa, Perú',
            'telefono': '+51 54 234567',
            'email': 'contacto@pampabaja.com.pe',
            'contacto': 'Jorge Medina',
            'observaciones': 'Proveedor premium de paltas peruanas',
            'business': business
        }
    )
    if created:
        print(f"✓ Proveedor creado: {proveedor.nombre}")
    else:
        print(f"ℹ️ Proveedor ya existe: {proveedor.nombre}")
    
    # 5. Crear recepción de mercadería
    # Verificar si ya existe una recepción con el mismo número de guía
    numero_guia = 'GE-2025-001'
    if GoodsReception.objects.filter(numero_guia=numero_guia).exists():
        print(f"ℹ️ Ya existe una recepción con el número de guía {numero_guia}")
        recepcion = GoodsReception.objects.get(numero_guia=numero_guia)
    else:
        recepcion = GoodsReception.objects.create(
            numero_guia=numero_guia,
            proveedor=proveedor,
            numero_guia_proveedor='PB-EXP-2025-456',
            recibido_por=admin_user,
            estado='pendiente',
            observaciones='Recepción de 6 pallets de paltas peruanas marca Pampa Baja',
            business=business,
            total_pallets=0,  # Se actualizará automáticamente
            total_cajas=0,    # Se actualizará automáticamente
            total_peso_bruto=Decimal('0')  # Se actualizará automáticamente
        )
        print(f"✓ Recepción de mercadería creada: {recepcion.numero_guia}")
    
    # 6. Crear detalles de recepción (6 pallets)
    # Configuración de pallets según especificaciones
    pallets_config = [
        # 2 pallets calibre 20
        {'calibre': '20', 'numero_pallet': 'PB-001', 'cantidad_cajas': 104, 'peso_bruto': Decimal('1040'), 'precio': Decimal('1950')},
        {'calibre': '20', 'numero_pallet': 'PB-002', 'cantidad_cajas': 104, 'peso_bruto': Decimal('1040'), 'precio': Decimal('1980')},
        # 2 pallets calibre 18
        {'calibre': '18', 'numero_pallet': 'PB-003', 'cantidad_cajas': 104, 'peso_bruto': Decimal('1040'), 'precio': Decimal('2000')},
        {'calibre': '18', 'numero_pallet': 'PB-004', 'cantidad_cajas': 104, 'peso_bruto': Decimal('1040'), 'precio': Decimal('2050')},
        # 2 pallets calibre 16
        {'calibre': '16', 'numero_pallet': 'PB-005', 'cantidad_cajas': 104, 'peso_bruto': Decimal('1040'), 'precio': Decimal('2080')},
        {'calibre': '16', 'numero_pallet': 'PB-006', 'cantidad_cajas': 104, 'peso_bruto': Decimal('1040'), 'precio': Decimal('2100')},
    ]
    
    # Crear los detalles de recepción
    for pallet_config in pallets_config:
        # Verificar si ya existe este detalle
        if ReceptionDetail.objects.filter(
            recepcion=recepcion, 
            numero_pallet=pallet_config['numero_pallet']
        ).exists():
            print(f"ℹ️ Ya existe un detalle para el pallet {pallet_config['numero_pallet']}")
            continue
        
        # Crear el detalle de recepción
        detalle = ReceptionDetail.objects.create(
            recepcion=recepcion,
            producto=producto,
            variedad='Hass',
            calibre=pallet_config['calibre'],
            numero_pallet=pallet_config['numero_pallet'],
            cantidad_cajas=pallet_config['cantidad_cajas'],
            peso_bruto=pallet_config['peso_bruto'],
            peso_tara=Decimal('25.0') + (Decimal('0.5') * pallet_config['cantidad_cajas']),  # Peso pallet + peso cajas
            calidad=5,  # Excelente
            temperatura=Decimal('8.5'),
            estado_maduracion='verde',
            observaciones=f'Pallet de paltas calibre {pallet_config["calibre"]} en estado verde, precio por kilo: ${pallet_config["precio"]}'
        )
        print(f"✓ Detalle de recepción creado: Pallet {detalle.numero_pallet} - Calibre {detalle.calibre}")
    
    # 7. Actualizar totales de la recepción
    recepcion.actualizar_totales()
    print(f"✓ Totales actualizados: {recepcion.total_pallets} pallets, {recepcion.total_cajas} cajas, {recepcion.total_peso_bruto} kg")
    
    # 8. Modificar la función crear_lotes_al_aprobar_recepcion para asignar el precio
    from django.db.models.signals import post_save
    from django.dispatch import receiver
    from inventory.models import MadurationHistory
    
    # Desconectar la señal original
    from inventory.models import crear_lotes_al_aprobar_recepcion
    post_save.disconnect(crear_lotes_al_aprobar_recepcion, sender=GoodsReception)
    
    # Definir una nueva función que asigne el precio
    @receiver(post_save, sender=GoodsReception)
    def crear_lotes_al_aprobar_recepcion_con_precio(sender, instance, **kwargs):
        """
        Versión modificada que extrae el precio de las observaciones del detalle
        """
        if instance.estado == "aprobado":
            # Procesar solo detalles que no tienen lote creado aún
            detalles_sin_lote = instance.detalles.filter(lote_creado__isnull=True)
            
            for detalle in detalles_sin_lote:
                # Verificar si ya existe un lote con el mismo QR code
                qr_code = f"LOT-{instance.numero_guia}-{detalle.numero_pallet}"
                existing_lot = FruitLot.objects.filter(qr_code=qr_code).first()
                
                if existing_lot:
                    print(f"\u2713 Ya existe un lote con QR {qr_code}, asignándolo al detalle")
                    detalle.lote_creado = existing_lot
                    detalle.save(update_fields=['lote_creado'])
                    continue
                
                # Extraer el precio de las observaciones
                precio = Decimal('0')
                if detalle.observaciones and 'precio por kilo: $' in detalle.observaciones:
                    try:
                        precio_str = detalle.observaciones.split('precio por kilo: $')[1].split('}')[0]
                        precio = Decimal(precio_str)
                    except (IndexError, ValueError):
                        pass
                
                # Crear un nuevo lote de fruta basado en el detalle de recepción
                try:
                    lote = FruitLot(
                        producto=detalle.producto,
                        marca=detalle.variedad or "",
                        proveedor=instance.proveedor.nombre,
                        procedencia=instance.proveedor.direccion or "No especificada",
                        pais="Perú",  # Cambiado a Perú para las paltas peruanas
                        calibre=detalle.calibre or "No especificado",
                        box_type=detalle.producto.box_type if hasattr(detalle.producto, 'box_type') else BoxType.objects.first(),
                        pallet_type=PalletType.objects.first(),
                        cantidad_cajas=detalle.cantidad_cajas,
                        peso_bruto=detalle.peso_bruto,
                        peso_neto=detalle.peso_neto,
                        qr_code=qr_code,
                        business=instance.business,
                        fecha_ingreso=instance.fecha_recepcion.date(),
                        estado_maduracion=detalle.estado_maduracion or "verde",
                        costo_inicial=precio,  # Asignar el precio extraído
                        costo_diario_almacenaje=Decimal('10.0'),  # Valor por defecto
                        estado_lote='activo'  # Nuevo campo para el estado del lote
                    )
                    
                    # Guardar el lote y actualizar la referencia en el detalle
                    lote.save()
                    
                    # Registrar el cambio de estado de maduración inicial
                    MadurationHistory.objects.create(
                        lote=lote,
                        estado_maduracion=lote.estado_maduracion
                    )
                    
                    # Actualizar el detalle con referencia al lote creado
                    detalle.lote_creado = lote
                    detalle.save(update_fields=['lote_creado'])
                    
                    print(f"\u2713 Lote creado automáticamente: {lote} con precio {precio} desde recepción {instance.numero_guia}")
                except Exception as e:
                    print(f"\u274c Error al crear lote para pallet {detalle.numero_pallet}: {str(e)}")
                    continue
    
    # 9. Aprobar la recepción para generar los lotes automáticamente
    if recepcion.estado != 'aprobado':
        recepcion.estado = 'aprobado'
        recepcion.revisado_por = admin_user
        recepcion.save()
        print(f"\u2713 Recepción aprobada: Se generarán los lotes automáticamente")
        
    # Restaurar la función original
    post_save.disconnect(crear_lotes_al_aprobar_recepcion_con_precio, sender=GoodsReception)
    post_save.connect(crear_lotes_al_aprobar_recepcion, sender=GoodsReception)
    
    # 10. Verificar que los lotes se hayan creado correctamente
    lotes = FruitLot.objects.filter(producto=producto)
    print(f"\n\u2713 Total de lotes creados/existentes: {lotes.count()}")
    
    print("\n\u2713 Seed de inventario completado con éxito!")

if __name__ == "__main__":
    create_inventory_seed()
