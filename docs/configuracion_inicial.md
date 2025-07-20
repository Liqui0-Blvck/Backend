# Guía de Configuración Inicial de FruitPOS

Este documento describe el proceso para configurar correctamente la base de datos de FruitPOS con usuarios y empresas iniciales, así como los pasos a seguir cuando se encuentran problemas con la base de datos.

## Índice

1. [Estructura del Sistema](#estructura-del-sistema)
2. [Proceso de Configuración](#proceso-de-configuración)
3. [Solución de Problemas Comunes](#solución-de-problemas-comunes)
4. [Scripts de Utilidad](#scripts-de-utilidad)

## Estructura del Sistema

### Modelos Principales

- **CustomUser**: Extiende AbstractUser, usa email como identificador principal, tiene un campo `role` con opciones admin, supervisor, vendedor y visualizador.
- **Perfil**: Conecta usuarios con empresas, tiene OneToOne con CustomUser y ForeignKey a Business.
- **Business**: Representa las empresas en el sistema, con campos como nombre, rut, email, teléfono, dirección y dueño (FK a Perfil).

### Relaciones Importantes

- El negocio (business) del usuario se accede a través del modelo Perfil (`perfil.business`) y no directamente desde el usuario.
- El dueño de un negocio es un perfil de usuario (`business.dueno`).
- Los usuarios pueden tener múltiples roles, pero solo uno se guarda como principal en el campo `role` del usuario.

## Proceso de Configuración

### 1. Preparación del Entorno

```bash
# Asegurarse de que los contenedores estén construidos con la última versión del código
docker-compose build

# Iniciar los contenedores
docker-compose up -d

# Verificar que la base de datos esté lista
docker exec -it backend-db-1 pg_isready
```

### 2. Aplicar Migraciones

Es crucial asegurarse de que todas las migraciones estén aplicadas antes de intentar crear usuarios o empresas:

```bash
# Aplicar todas las migraciones pendientes
docker exec -it backend-api-1 python manage.py migrate

# Verificar el estado de las migraciones
docker exec -it backend-api-1 python manage.py showmigrations
```

### 3. Creación de Usuarios

Utilizamos el script `run_seeds.py` para crear usuarios con diferentes roles:

```bash
# Copiar el script al contenedor
docker cp /ruta/local/scripts/run_seeds.py backend-api-1:/app/scripts/run_seeds.py

# Ejecutar el script
docker exec -it backend-api-1 python /app/scripts/run_seeds.py
```

El script `run_seeds.py` realiza las siguientes acciones:
- Crea usuarios con sus respectivos roles
- Maneja usuarios con múltiples roles, asignando el primero como principal
- Crea perfiles asociados a cada usuario

### 4. Creación de Empresas

Utilizamos el script `create_business.py` para crear empresas y asignar usuarios:

```bash
# Copiar el script al contenedor
docker cp /ruta/local/scripts/create_business.py backend-api-1:/app/scripts/create_business.py

# Ejecutar el script
docker exec -it backend-api-1 python /app/scripts/create_business.py
```

El script `create_business.py` realiza las siguientes acciones:
- Crea empresas con todos sus datos (nombre, rut, email, teléfono, dirección)
- Asigna el primer administrador como dueño de la empresa
- Asigna todos los usuarios a sus respectivas empresas

## Solución de Problemas Comunes

### Problema: Error "column does not exist"

**Síntoma**: Al ejecutar scripts, aparecen errores indicando que una columna no existe en la base de datos.

**Solución**:
1. Verificar que todas las migraciones estén aplicadas:
   ```bash
   docker exec -it backend-api-1 python manage.py showmigrations
   ```
2. Si hay migraciones pendientes, aplicarlas:
   ```bash
   docker exec -it backend-api-1 python manage.py migrate
   ```
3. Si el modelo en el código tiene campos que no existen en la base de datos, crear una nueva migración:
   ```bash
   docker exec -it backend-api-1 python manage.py makemigrations
   ```

### Problema: Error "InvalidCursorName"

**Síntoma**: Al intentar crear perfiles o acceder al panel de administración, aparece un error "InvalidCursorName".

**Solución**:
1. Reiniciar el contenedor de la API:
   ```bash
   docker restart backend-api-1
   ```
2. Asegurarse de que la base de datos esté funcionando correctamente:
   ```bash
   docker exec -it backend-db-1 pg_isready
   ```

### Problema: Error "null value in column violates not-null constraint"

**Síntoma**: Al crear empresas, aparece un error indicando que un campo no puede ser nulo.

**Solución**:
1. Identificar qué campo no puede ser nulo (ej: dueno_id)
2. Modificar el script para asignar un valor a ese campo antes de guardar el objeto
3. Si es necesario, crear primero los objetos relacionados (ej: perfiles de usuario)

## Scripts de Utilidad

### inspect_db.py

Este script permite inspeccionar la estructura real de las tablas en la base de datos:

```python
#!/usr/bin/env python
import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
sys.path.append('/app')
django.setup()

from django.db import connection

def inspect_table(table_name):
    with connection.cursor() as cursor:
        cursor.execute(f"""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = '{table_name}'
            ORDER BY ordinal_position;
        """)
        columns = cursor.fetchall()
        
        print(f"Estructura de la tabla {table_name}:")
        for column in columns:
            print(f"{column[0]}: {column[1]}")

if __name__ == "__main__":
    inspect_table('business_business')
    print("\n")
    inspect_table('accounts_perfil')
```

### run_seeds.py

Script para crear usuarios iniciales con sus roles y perfiles:

```python
#!/usr/bin/env python
import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
sys.path.append('/app')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import Perfil

User = get_user_model()

def create_users_from_seed():
    # Definir usuarios con sus roles
    users_data = [
        # Usuarios de Prohas
        {"email": "admin1@prohas.cl", "password": "admin123", "first_name": "Admin1", "last_name": "Prohas", "role": "admin"},
        {"email": "admin2@prohas.cl", "password": "admin123", "first_name": "Admin2", "last_name": "Prohas", "role": "admin"},
        {"email": "supervisor@prohas.cl", "password": "super123", "first_name": "Super", "last_name": "Prohas", "role": "supervisor,vendedor"},
        {"email": "vendedor1@prohas.cl", "password": "vend123", "first_name": "Vendedor1", "last_name": "Prohas", "role": "vendedor"},
        # ... más usuarios
    ]
    
    for user_data in users_data:
        # Extraer roles
        roles = user_data["role"].split(",")
        primary_role = roles[0]
        
        # Notificar si hay múltiples roles
        if len(roles) > 1:
            print(f"⚠️ Usuario {user_data['email']} tiene múltiples roles: {', '.join(roles)}")
            print(f"  Nota: Se ha asignado '{primary_role}' como rol principal en el sistema.")
            print(f"  Los roles adicionales deberán ser gestionados manualmente en la aplicación.")
        
        # Crear usuario si no existe
        user, created = User.objects.get_or_create(
            email=user_data["email"],
            defaults={
                "first_name": user_data["first_name"],
                "last_name": user_data["last_name"],
                "role": primary_role
            }
        )
        
        if created:
            user.set_password(user_data["password"])
            user.save()
            
            # Crear perfil si no existe
            Perfil.objects.get_or_create(
                user=user,
                defaults={
                    "phone": user_data.get("phone", ""),
                    "rut": user_data.get("rut", "")
                }
            )
            
            print(f"✓ Usuario creado: {user.email} (Rol: {user.role})")
        else:
            print(f"⚠️ Usuario {user.email} ya existe, no se ha modificado.")

if __name__ == "__main__":
    print("Creando usuarios iniciales desde los datos de semilla...")
    create_users_from_seed()
    print("\nUsuarios creados con éxito!")
```

### create_business.py

Script para crear empresas y asignar usuarios:

```python
#!/usr/bin/env python
import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
sys.path.append('/app')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import Perfil
from business.models import Business

User = get_user_model()

def create_businesses():
    # Datos de las empresas
    businesses_data = [
        {
            'nombre': 'Prohas',
            'rut': '76.123.456-7',
            'email': 'contacto@prohas.cl',
            'telefono': '+56912345678',
            'direccion': 'Av. Las Paltas 123, Santiago',
            'admin_emails': ['admin1@prohas.cl', 'admin2@prohas.cl'],
            'supervisor_emails': ['supervisor@prohas.cl'],
            'vendedor_emails': ['supervisor@prohas.cl', 'vendedor1@prohas.cl', 'vendedor2@prohas.cl', 'vendedor3@prohas.cl', 'vendedor4@prohas.cl']
        },
        # ... más empresas
    ]
    
    for business_data in businesses_data:
        try:
            # Verificar si la empresa ya existe
            existing_business = Business.objects.filter(rut=business_data['rut']).first()
            
            if existing_business:
                business = existing_business
            else:
                # Encontrar el perfil del primer administrador
                admin_email = business_data['admin_emails'][0]
                admin_user = User.objects.filter(email=admin_email).first()
                admin_perfil = Perfil.objects.filter(user=admin_user).first()
                
                # Crear la empresa con todos los campos disponibles
                business = Business(
                    nombre=business_data['nombre'],
                    rut=business_data['rut'],
                    email=business_data['email'],
                    telefono=business_data['telefono'],
                    direccion=business_data['direccion'],
                    dueno=admin_perfil
                )
                business.save()
                
                # Asignar la empresa al perfil del dueño
                admin_perfil.business = business
                admin_perfil.save()
            
            # Asignar usuarios a la empresa (excepto el dueño)
            all_user_emails = set(
                business_data['admin_emails'][1:] +
                business_data['supervisor_emails'] + 
                business_data['vendedor_emails']
            )
            
            for email in all_user_emails:
                user = User.objects.filter(email=email).first()
                if user:
                    perfil = Perfil.objects.filter(user=user).first()
                    if perfil:
                        perfil.business = business
                        perfil.save()
                
        except Exception as e:
            print(f"❌ Error al procesar la empresa {business_data['nombre']}: {str(e)}")

if __name__ == "__main__":
    create_businesses()
```

---

Este documento fue creado el 1 de julio de 2025 como guía para la configuración inicial del sistema FruitPOS.
