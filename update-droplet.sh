#!/bin/bash
set -e

# Colores para mensajes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuración
DROPLET_IP="143.198.73.247"
SSH_USER="root"
REMOTE_DIR="/opt/fruitpos"

echo -e "${GREEN}=== Actualizando FruitPOS API en el droplet ===${NC}"

# 1. Crear archivo docker-compose.production.yml actualizado
echo -e "${YELLOW}Creando docker-compose.production.yml actualizado...${NC}"
cat > /tmp/docker-compose.production.yml << 'EOF'
version: '3.8'

services:
  # Servicio db eliminado - usando base de datos administrada de DigitalOcean

  redis:
    image: redis:7-alpine
    restart: always
    volumes:
      - redis_prod_data:/data
    # Configuración optimizada para producción
    command: >
      redis-server
      --appendonly yes
      --appendfsync everysec
      --maxmemory 512mb
      --maxmemory-policy allkeys-lru

  api:
    build: .
    restart: always
    # Usar el entrypoint que maneja migraciones y collectstatic
    command: ["/app/docker-entrypoint.sh"]
    volumes:
      # Solo logs para producción (no montar código fuente)
      - ./logs:/app/logs
      # Certificados SSL si es necesario
      - ./ssl:/app/ssl:ro
    expose:
      - "8000"
    depends_on:
      - redis
    environment:
      # Configuración básica de Django
      DJANGO_SETTINGS_MODULE: backend.settings
      DJANGO_ENV: production
      
      # Base de datos (producción con prefijo P_)
      P_POSTGRES_DB: ${P_POSTGRES_DB}
      P_POSTGRES_USER: ${P_POSTGRES_USER}
      P_POSTGRES_PASSWORD: ${P_POSTGRES_PASSWORD}
      P_POSTGRES_HOST: ${P_POSTGRES_HOST}
      P_POSTGRES_PORT: ${P_POSTGRES_PORT}
      
      # Redis (producción)
      P_REDIS_URL: ${P_REDIS_URL:-redis://redis:6379/0}
      
      # DigitalOcean Spaces (OBLIGATORIO en producción)
      P_USE_SPACES: ${P_USE_SPACES:-True}
      P_SPACES_ACCESS_KEY_ID: ${P_SPACES_ACCESS_KEY_ID}
      P_SPACES_SECRET_ACCESS_KEY: ${P_SPACES_SECRET_ACCESS_KEY}
      P_SPACES_BUCKET_NAME: ${P_SPACES_BUCKET_NAME:-fruitpost}
      P_SPACES_ENDPOINT_URL: ${P_SPACES_ENDPOINT_URL:-https://sfo3.digitaloceanspaces.com}
      P_SPACES_REGION: ${P_SPACES_REGION:-sfo3}
      P_SPACES_CDN_DOMAIN: ${P_SPACES_CDN_DOMAIN}
      
      # CORS para producción
      P_CORS_ALLOWED_ORIGINS: ${P_CORS_ALLOWED_ORIGINS:-https://fruitpos.cl,https://www.fruitpos.cl}
      
      # Configuración de seguridad
      P_SECURE_SSL_REDIRECT: ${P_SECURE_SSL_REDIRECT:-True}
      
      # Email para producción
      P_EMAIL_BACKEND: ${P_EMAIL_BACKEND:-django.core.mail.backends.smtp.EmailBackend}
      P_EMAIL_HOST: ${P_EMAIL_HOST:-smtp.gmail.com}
      P_EMAIL_PORT: ${P_EMAIL_PORT:-587}
      P_EMAIL_USE_TLS: ${P_EMAIL_USE_TLS:-True}
      P_EMAIL_HOST_USER: ${P_EMAIL_HOST_USER:-}
      P_EMAIL_HOST_PASSWORD: ${P_EMAIL_HOST_PASSWORD:-}
      P_DEFAULT_FROM_EMAIL: ${P_DEFAULT_FROM_EMAIL:-noreply@fruitpos.cl}
      
      # Logging para producción
      P_LOG_FILE: ${P_LOG_FILE:-/app/logs/django.log}
      P_DJANGO_LOG_LEVEL: ${P_DJANGO_LOG_LEVEL:-WARNING}
      
      # Debug SIEMPRE False en producción
      DEBUG: "False"
      
      # Clave secreta (OBLIGATORIO cambiar en producción)
      SECRET_KEY: ${SECRET_KEY}
      
      # Hosts permitidos
      ALLOWED_HOSTS: ${ALLOWED_HOSTS:-fruitpos.cl,www.fruitpos.cl,api.fruitpos.cl}

  nginx:
    image: nginx:1.25-alpine
    restart: always
    ports:
      - "80:80"        # Puerto HTTP (redirige a HTTPS)
      - "443:443"      # Puerto HTTPS
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro  # Certificados SSL
      # NO montar static/media porque se sirven desde DigitalOcean Spaces
    depends_on:
      - api
    environment:
      - NGINX_HOST=fruitpos.cl
      - NGINX_PORT=443
    # Configuración de salud para nginx
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost/health/"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Servicio opcional para collectstatic inicial
  collectstatic:
    build: .
    command: ["python", "manage.py", "collectstatic", "--noinput"]
    volumes:
      - ./logs:/app/logs
    environment:
      # Mismas variables que api para acceder a Spaces
      DJANGO_SETTINGS_MODULE: backend.settings
      P_POSTGRES_DB: ${P_POSTGRES_DB}
      P_POSTGRES_USER: ${P_POSTGRES_USER}
      P_POSTGRES_PASSWORD: ${P_POSTGRES_PASSWORD}
      P_POSTGRES_HOST: ${P_POSTGRES_HOST}
      P_POSTGRES_PORT: ${P_POSTGRES_PORT}
      P_USE_SPACES: ${P_USE_SPACES:-True}
      P_SPACES_ACCESS_KEY_ID: ${P_SPACES_ACCESS_KEY_ID}
      P_SPACES_SECRET_ACCESS_KEY: ${P_SPACES_SECRET_ACCESS_KEY}
      P_SPACES_BUCKET_NAME: ${P_SPACES_BUCKET_NAME:-fruitpost}
      P_SPACES_ENDPOINT_URL: ${P_SPACES_ENDPOINT_URL:-https://sfo3.digitaloceanspaces.com}
      P_SPACES_REGION: ${P_SPACES_REGION:-sfo3}
      P_SPACES_CDN_DOMAIN: ${P_SPACES_CDN_DOMAIN}
      SECRET_KEY: ${SECRET_KEY}
      DEBUG: "False"
    profiles:
      - tools  # Solo ejecutar manualmente con --profile tools

volumes:
  redis_prod_data:
    driver: local

# Configuración de red para producción
networks:
  default:
    driver: bridge
    ipam:
      config:
        - subnet: 172.30.0.0/16  # Cambiado para evitar conflictos
EOF

# 2. Crear archivo nginx.conf actualizado
echo -e "${YELLOW}Creando nginx.conf actualizado...${NC}"
cat > /tmp/nginx.conf << 'EOF'
server {
    listen 80;
    server_name fruitpos.cl www.fruitpos.cl api.fruitpos.cl;

    # Redirigir todo el tráfico HTTP a HTTPS (comentar si no tienes SSL configurado)
    # return 301 https://$host$request_uri;

    # Configuración básica
    client_max_body_size 100M;

    # Archivos estáticos y media (servidos desde DigitalOcean Spaces)
    location /static/ {
        proxy_pass https://fruitpost.sfo3.cdn.digitaloceanspaces.com/fruitpos/static/;
        proxy_set_header Host fruitpost.sfo3.cdn.digitaloceanspaces.com;
        proxy_cache_valid 200 60m;
        expires 1d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        proxy_pass https://fruitpost.sfo3.cdn.digitaloceanspaces.com/fruitpos/media/;
        proxy_set_header Host fruitpost.sfo3.cdn.digitaloceanspaces.com;
        proxy_cache_valid 200 60m;
        expires 1d;
        add_header Cache-Control "public";
    }

    # WebSocket
    location /ws/ {
        proxy_pass http://api:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }

    # API y aplicación principal
    location / {
        proxy_pass http://api:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }

    # Endpoint de salud para monitoreo
    location /health/ {
        access_log off;
        return 200 "healthy\n";
    }
}

# Configuración para HTTPS (descomentar cuando tengas certificados SSL)
# server {
#     listen 443 ssl http2;
#     server_name fruitpos.cl www.fruitpos.cl api.fruitpos.cl;
#     
#     # Configuración SSL/TLS
#     ssl_certificate /etc/nginx/ssl/fruitpos.crt;
#     ssl_certificate_key /etc/nginx/ssl/fruitpos.key;
#     
#     # Resto de la configuración igual que arriba...
# }
EOF

# 3. Transferir archivos al droplet
echo -e "${YELLOW}Transfiriendo archivos al droplet...${NC}"
scp /tmp/docker-compose.production.yml $SSH_USER@$DROPLET_IP:$REMOTE_DIR/
scp /tmp/nginx.conf $SSH_USER@$DROPLET_IP:$REMOTE_DIR/

# 4. Ejecutar comandos en el droplet
echo -e "${YELLOW}Ejecutando comandos en el droplet...${NC}"
ssh $SSH_USER@$DROPLET_IP << 'ENDSSH'
cd /opt/fruitpos

# Detener contenedores existentes
echo "Deteniendo contenedores existentes..."
docker-compose -f docker-compose.production.yml down || true

# Limpiar redes Docker
echo "Limpiando redes Docker no utilizadas..."
docker network prune -f

# Reiniciar Docker si es necesario
echo "Reiniciando Docker..."
systemctl restart docker

# Desplegar con el archivo actualizado
echo "Desplegando con el archivo actualizado..."
./deploy.sh -e prod -b
ENDSSH

echo -e "${GREEN}=== Actualización completada ===${NC}"
echo -e "${YELLOW}Para verificar el estado de los contenedores, ejecuta:${NC}"
echo -e "${GREEN}ssh $SSH_USER@$DROPLET_IP 'cd $REMOTE_DIR && docker-compose -f docker-compose.production.yml ps'${NC}"
echo -e "${YELLOW}Para ver los logs, ejecuta:${NC}"
echo -e "${GREEN}ssh $SSH_USER@$DROPLET_IP 'cd $REMOTE_DIR && docker-compose -f docker-compose.production.yml logs -f api'${NC}"
