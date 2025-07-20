# FruitPOS API

API backend para sistema de punto de venta de frutas, preparado para SaaS y desacoplado del frontend (Next.js).

## 🚀 Despliegue y desarrollo con Docker

### Producción con Nginx (opcional)

Para entornos productivos, puedes usar el servicio `nginx` incluido en el `docker-compose.yml`:

- Nginx actúa como proxy reverso para Daphne (ASGI), sirve archivos estáticos/media locales y puede terminar TLS si lo configuras.
- El archivo `nginx.conf` está listo para la mayoría de los despliegues.
- Accede a la API y WebSocket por el puerto 80.

```bash
docker compose up --build
```

Si usas DigitalOcean Spaces, los archivos media se sirven directamente desde el CDN de Spaces.

---

### 1. Variables de entorno

Copia `.env.example` a `.env` y completa tus valores reales:
```bash
cp .env.example .env
```

- Para desarrollo local puedes usar SQLite y media local.
- Para producción (DigitalOcean):
  - Usa Postgres y Redis gestionados.
  - Usa DigitalOcean Spaces para media.
  - Asegúrate de tener `DJANGO_ENV=production` y `DEBUG=False`.

### 2. Levantar el stack completo

```bash
docker compose up --build
```
Esto construirá la imagen, aplicará migraciones, hará collectstatic y levantará el servidor ASGI (Daphne) con soporte WebSocket.

### 3. Servicios incluidos
- **api**: Django + Channels (ASGI, WebSocket, HTTP)
- **db**: Postgres persistente
- **redis**: Redis para Channels

### 4. Migraciones y estáticos
Las migraciones y collectstatic se ejecutan automáticamente al iniciar el contenedor `api`.

### 5. Acceso
- API: http://localhost:8000/
- Admin: http://localhost:8000/admin/

### 6. Personalización
- Cambia los valores de `.env` según tu entorno.
- Puedes conectar a bases de datos gestionadas de DigitalOcean cambiando los valores de `POSTGRES_HOST`, `POSTGRES_PORT`, `REDIS_URL`.

---

## 🗃️ Notas sobre almacenamiento de archivos
- En producción, los archivos se guardan en DigitalOcean Spaces (S3 compatible).
- En desarrollo, se usan carpetas locales (`media/`).
- El campo `url` de los archivos es público y puede ser consumido directo desde el frontend (Next.js).

---

## 🧩 Comandos útiles

- Ejecutar comandos dentro del contenedor:
  ```bash
  docker compose exec api bash
  # Ejemplo: crear superusuario
  python manage.py createsuperuser
  ```
- Ver logs:
  ```bash
  docker compose logs -f api
  ```
- Parar y limpiar:
  ```bash
  docker compose down -v
  ```

---

## 🌎 Despliegue en DigitalOcean

- Sube tu imagen a un Container Registry o conecta el repo a App Platform.
- Usa los servicios gestionados de Postgres y Redis.
- Configura las variables de entorno desde el panel de DO.
- Asegúrate de exponer el puerto 8000 y usar Daphne (ASGI).
- Configura CORS para tu frontend Next.js.

---

¿Dudas o necesitas ayuda para el despliegue? ¡Escríbeme!

## Estructura de apps
- `core`: configuración general y utilidades
- `accounts`: usuarios y roles personalizados
- `business`: empresas (multi-tenant)
- `inventory`: gestión de fruta por lotes y cajas
- `sales`: ventas por lote
- `shifts`: turnos de trabajo
- `reports`: generación de reportes
- `media`: carga de imágenes
- `whatsapp`: integración con Twilio/IA

## Stack
- Django 4+
- Django REST Framework
- djangorestframework-simplejwt
- django-cors-headers
- Twilio SDK

## Instalación rápida
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Endpoints principales
- `/api/v1/fruits/`
- `/api/v1/sales/`
- `/api/v1/shifts/`
- `/api/v1/reports/`
- `/api/v1/whatsapp/`

## Notas
- JWT para autenticación
- Multi-tenant: cada recurso ligado a una empresa
- CORS activo para frontend Next.js
