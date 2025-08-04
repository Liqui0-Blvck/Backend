#!/bin/bash

# ==============================================
# Script de Despliegue con DigitalOcean Spaces
# ==============================================

set -e  # Salir si hay algún error

echo "🚀 Iniciando despliegue de FruitPOS con DigitalOcean Spaces..."

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Función para mostrar mensajes
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Verificar que estamos en el directorio correcto
if [ ! -f "docker-compose.production.yml" ]; then
    log_error "No se encontró docker-compose.production.yml. Ejecuta este script desde el directorio raíz del proyecto."
    exit 1
fi

# Verificar variables de entorno obligatorias
log_info "Verificando variables de entorno obligatorias..."

required_vars=(
    "P_POSTGRES_PASSWORD"
    "P_SPACES_ACCESS_KEY_ID"
    "P_SPACES_SECRET_ACCESS_KEY"
    "SECRET_KEY"
)

missing_vars=()
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -ne 0 ]; then
    log_error "Faltan las siguientes variables de entorno obligatorias:"
    for var in "${missing_vars[@]}"; do
        echo "  - $var"
    done
    echo ""
    log_info "Configura estas variables antes de continuar:"
    echo "  export P_POSTGRES_PASSWORD='tu-password-seguro'"
    echo "  export P_SPACES_ACCESS_KEY_ID='tu-spaces-access-key'"
    echo "  export P_SPACES_SECRET_ACCESS_KEY='tu-spaces-secret-key'"
    echo "  export SECRET_KEY='tu-django-secret-key'"
    exit 1
fi

log_success "Variables de entorno verificadas"

# Verificar que DigitalOcean Spaces esté configurado
log_info "Verificando configuración de DigitalOcean Spaces..."

if [ -z "$P_SPACES_BUCKET_NAME" ]; then
    export P_SPACES_BUCKET_NAME="fruitpost"
    log_warning "P_SPACES_BUCKET_NAME no configurado, usando: $P_SPACES_BUCKET_NAME (ENDPOINT REAL DEL USUARIO)"
fi

if [ -z "$P_SPACES_ENDPOINT_URL" ]; then
    export P_SPACES_ENDPOINT_URL="https://sfo3.digitaloceanspaces.com"
    log_warning "P_SPACES_ENDPOINT_URL no configurado, usando: $P_SPACES_ENDPOINT_URL (ENDPOINT REAL DEL USUARIO)"
fi

if [ -z "$P_SPACES_REGION" ]; then
    export P_SPACES_REGION="sfo3"
    log_warning "P_SPACES_REGION no configurado, usando: $P_SPACES_REGION (REGIÓN REAL DEL USUARIO)"
fi

if [ -z "$P_SPACES_CDN_DOMAIN" ]; then
    export P_SPACES_CDN_DOMAIN="$P_SPACES_BUCKET_NAME.sfo3.cdn.digitaloceanspaces.com"
    log_warning "P_SPACES_CDN_DOMAIN no configurado, usando: $P_SPACES_CDN_DOMAIN (CDN REAL DEL USUARIO)"
fi

log_success "Configuración de Spaces verificada"

# Verificar certificados SSL
log_info "Verificando certificados SSL..."

if [ ! -f "ssl/fruitpos.crt" ] || [ ! -f "ssl/fruitpos.key" ]; then
    log_warning "Certificados SSL no encontrados. Generando certificados auto-firmados..."
    ./scripts/generate-ssl-certs.sh
else
    log_success "Certificados SSL encontrados"
fi

# Crear directorio de logs si no existe
mkdir -p logs
log_success "Directorio de logs creado"

# Construir imágenes Docker
log_info "Construyendo imágenes Docker..."
docker-compose -f docker-compose.production.yml build --no-cache

log_success "Imágenes Docker construidas"

# Detener servicios existentes si están corriendo
log_info "Deteniendo servicios existentes..."
docker-compose -f docker-compose.production.yml down --remove-orphans || true

log_success "Servicios existentes detenidos"

# Iniciar servicios de base de datos primero
log_info "Iniciando servicios de base de datos..."
docker-compose -f docker-compose.production.yml up -d db redis

# Esperar a que la base de datos esté lista
log_info "Esperando a que la base de datos esté lista..."
sleep 10

# Ejecutar migraciones
log_info "Ejecutando migraciones de base de datos..."
docker-compose -f docker-compose.production.yml run --rm api python manage.py migrate

log_success "Migraciones ejecutadas"

# Crear superusuario si no existe
log_info "Verificando superusuario..."
docker-compose -f docker-compose.production.yml run --rm api python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser('admin@fruitpos.cl', 'admin@fruitpos.cl', 'admin123')
    print('Superusuario creado: admin@fruitpos.cl / admin123')
else:
    print('Superusuario ya existe')
"

# Ejecutar collectstatic para subir archivos a Spaces
log_info "Subiendo archivos estáticos a DigitalOcean Spaces..."
docker-compose -f docker-compose.production.yml run --rm --profile tools collectstatic

log_success "Archivos estáticos subidos a Spaces"

# Ejecutar seeds si existen
if [ -f "scripts/run_seeds.py" ]; then
    log_info "Ejecutando seeds de datos..."
    docker-compose -f docker-compose.production.yml run --rm api python scripts/run_seeds.py || log_warning "Seeds fallaron o no son necesarios"
fi

# Iniciar todos los servicios
log_info "Iniciando todos los servicios..."
docker-compose -f docker-compose.production.yml up -d

log_success "Servicios iniciados"

# Esperar a que los servicios estén listos
log_info "Esperando a que los servicios estén listos..."
sleep 15

# Verificar que los servicios estén funcionando
log_info "Verificando estado de los servicios..."

# Verificar API
if curl -f -s http://localhost/api/v1/ > /dev/null; then
    log_success "API funcionando correctamente"
else
    log_warning "API no responde, verifica los logs"
fi

# Verificar HTTPS
if curl -f -s -k https://localhost/ > /dev/null; then
    log_success "HTTPS funcionando correctamente"
else
    log_warning "HTTPS no responde, verifica los certificados"
fi

# Mostrar información de despliegue
echo ""
echo "🎉 ¡Despliegue completado!"
echo ""
echo "📋 Información del despliegue:"
echo "  🌐 Dominio: fruitpos.cl"
echo "  🔒 HTTPS: Habilitado"
echo "  📦 DigitalOcean Spaces: Habilitado"
echo "  🗄️  Bucket: $P_SPACES_BUCKET_NAME"
echo "  🚀 CDN: $P_SPACES_CDN_DOMAIN"
echo ""
echo "🔗 URLs importantes:"
echo "  • Frontend: https://fruitpos.cl"
echo "  • API: https://api.fruitpos.cl/api/v1/"
echo "  • Admin: https://api.fruitpos.cl/admin/"
echo "  • Archivos estáticos: https://$P_SPACES_CDN_DOMAIN/fruitpos/static/"
echo "  • Archivos media: https://$P_SPACES_CDN_DOMAIN/fruitpos/media/"
echo ""
echo "👤 Credenciales de admin:"
echo "  • Email: admin@fruitpos.cl"
echo "  • Password: admin123"
echo "  • ⚠️  CAMBIAR PASSWORD EN PRODUCCIÓN"
echo ""
echo "📊 Comandos útiles:"
echo "  • Ver logs: docker-compose -f docker-compose.production.yml logs -f"
echo "  • Reiniciar: docker-compose -f docker-compose.production.yml restart"
echo "  • Detener: docker-compose -f docker-compose.production.yml down"
echo "  • Actualizar archivos estáticos: docker-compose -f docker-compose.production.yml run --rm --profile tools collectstatic"
echo ""

log_success "¡FruitPOS está listo para producción con DigitalOcean Spaces!"
