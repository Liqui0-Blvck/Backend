#!/usr/bin/env python3
import re

file_path = 'sales/serializers.py'

with open(file_path, 'r') as f:
    content = f.read()

# Reemplazar get_producto_nombre
content = re.sub(
    r'def get_producto_nombre\(self, obj\):\s+if obj\.lote and obj\.lote\.producto:\s+return obj\.lote\.producto\.nombre\s+return None',
    'def get_producto_nombre(self, obj):\n        # Obtener desde el primer item\n        first_item = obj.items.first()\n        if first_item and first_item.lote and first_item.lote.producto:\n            return first_item.lote.producto.nombre\n        return None',
    content
)

# Reemplazar get_calibre
content = re.sub(
    r'def get_calibre\(self, obj\):\s+if obj\.lote:\s+return obj\.lote\.calibre\s+return None',
    'def get_calibre(self, obj):\n        # Obtener desde el primer item\n        first_item = obj.items.first()\n        if first_item and first_item.lote:\n            return first_item.lote.calibre\n        return None',
    content
)

# Reemplazar get_lote_info si existe
if 'def get_lote_info' in content:
    content = re.sub(
        r'def get_lote_info\(self, obj\):[^}]*?return FruitLotSerializer\(obj\.lote\)\.data',
        'def get_lote_info(self, obj):\n        first_item = obj.items.first()\n        if not first_item or not first_item.lote:\n            return None\n        return FruitLotSerializer(first_item.lote).data',
        content
    )

with open(file_path, 'w') as f:
    f.write(content)

print("Serializadores corregidos")
