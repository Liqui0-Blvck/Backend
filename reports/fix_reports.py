#!/usr/bin/env python3
import re

# Archivo a modificar
file_path = 'views.py'

# Leer el contenido del archivo
with open(file_path, 'r') as file:
    content = file.read()

# Reemplazar todas las ocurrencias de peso_vendido
replacements = [
    # Reemplazo 1: aggregate(total=Sum('peso_vendido'))
    (r"aggregate\(total=Sum\('peso_vendido'\)\)", 
     r"annotate(peso_total=Sum('items__peso_vendido')).aggregate(total=Sum('peso_total'))"),
    
    # Reemplazo 2: Sum(F('peso_vendido') * F('precio_kg')
    (r"Sum\(F\('peso_vendido'\) \* F\('precio_kg'\)", 
     r"Sum(F('items__peso_vendido') * F('items__precio_kg')"),
    
    # Reemplazo 3: venta.peso_vendido
    (r"venta\.peso_vendido", 
     r"venta.items.aggregate(total=Sum('peso_vendido'))['total'] or 0"),
]

# Aplicar los reemplazos
for old, new in replacements:
    content = re.sub(old, new, content)

# Guardar los cambios
with open(file_path + '.fixed', 'w') as file:
    file.write(content)

print("Archivo corregido guardado como", file_path + '.fixed')
