#!/bin/bash

# ==============================================
# Script de Despliegue en Servidor DigitalOcean
# ==============================================

set -e  # Salir si hay algún error

echo "🚀 Desplegando FruitPOS en servidor DigitalOcean..."

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

# Banner de bienvenida
echo "
╔══════════════════════════════════════════════════════════════╗
║                    🍎 FRUITPOS DEPLOYMENT 🍎                 ║
║              Despliegue en Servidor DigitalOcean             ║
╚══════════════════════════════════════════════════════════════╝
"

# Verificar que estamos en el directorio correcto
if [ ! -f "docker-compose.production.yml" ]; then
    log_error "No se encontró docker-compose.production.yml"
    log_info "Asegúrate de estar en el directorio raíz del proyecto FruitPOS"
    exit 1
fi

# Verificar que Docker esté instalado
if ! command -v docker &> /dev/null; then
    log_error "Docker no está instalado"
    log_info "Instala Docker primero: https://docs.docker.com/engine/install/"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    log_error "Docker Compose no está instalado"
    log_info "Instala Docker Compose primero"
    exit 1
fi

log_success "Docker y Docker Compose están instalados"

# Función para solicitar variables de entorno
request_env_vars() {
    echo ""
    log_info "Configuración de variables de entorno para producción"
    echo ""
    
    # PostgreSQL Password
    if [ -z "$P_POSTGRES_PASSWORD" ]; then
        echo -n "🔐 Ingresa una contraseña segura para PostgreSQL: "
        read -s P_POSTGRES_PASSWORD
        echo ""
        export P_POSTGRES_PASSWORD
    fi
    
    # Spaces Access Key
    if [ -z "$P_SPACES_ACCESS_KEY_ID" ]; then
        echo -n "🔑 Ingresa tu DigitalOcean Spaces Access Key ID: "
        read P_SPACES_ACCESS_KEY_ID
        export P_SPACES_ACCESS_KEY_ID
    fi
    
    # Spaces Secret Key
    if [ -z "$P_SPACES_SECRET_ACCESS_KEY" ]; then
        echo -n "🔐 Ingresa tu DigitalOcean Spaces Secret Access Key: "
        read -s P_SPACES_SECRET_ACCESS_KEY
        echo ""
        export P_SPACES_SECRET_ACCESS_KEY
    fi
    
    # Django Secret Key
    if [ -z "$SECRET_KEY" ]; then
        echo -n "🔑 Ingresa una clave secreta para Django (o presiona Enter para generar una): "
        read SECRET_KEY
        if [ -z "$SECRET_KEY" ]; then
            SECRET_KEY=$(python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())' 2>/dev/null || openssl rand -base64 32)
            log_info "Clave secreta generada automáticamente"
        fi
        export SECRET_KEY
    fi
    
    # Configurar valores por defecto para Spaces (tu configuración real)
    export P_SPACES_BUCKET_NAME="${P_SPACES_BUCKET_NAME:-fruitpost}"
    export P_SPACES_ENDPOINT_URL="${P_SPACES_ENDPOINT_URL:-https://sfo3.digitaloceanspaces.com}"
    export P_SPACES_REGION="${P_SPACES_REGION:-sfo3}"
    export P_SPACES_CDN_DOMAIN="${P_SPACES_CDN_DOMAIN:-fruitpost.sfo3.cdn.digitaloceanspaces.com}"
    export P_USE_SPACES="${P_USE_SPACES:-True}"
    
    # Otros valores por defecto
    export P_POSTGRES_DB="${P_POSTGRES_DB:-fruitpos_prod}"
    export P_POSTGRES_USER="${P_POSTGRES_USER:-fruitpos_user}"
    export P_POSTGRES_HOST="${P_POSTGRES_HOST:-db}"
    export P_POSTGRES_PORT="${P_POSTGRES_PORT:-5432}"
    export P_REDIS_URL="${P_REDIS_URL:-redis://redis:6379/0}"
    export ALLOWED_HOSTS="${ALLOWED_HOSTS:-fruitpos.cl,www.fruitpos.cl,api.fruitpos.cl}"
    export P_CORS_ALLOWED_ORIGINS="${P_CORS_ALLOWED_ORIGINS:-https://fruitpos.cl,https://www.fruitpos.cl}"
    
    log_success "Variables de entorno configuradas"
}

# Función para guardar variables en archivo
save_env_file() {
    log_info "Guardando variables de entorno en .env.production..."
    
    cat > .env.production << EOF
# Variables de producción para FruitPOS
# Generado automáticamente el $(date)

# Base de datos
export P_POSTGRES_DB="$P_POSTGRES_DB"
export P_POSTGRES_USER="$P_POSTGRES_USER"
export P_POSTGRES_PASSWORD="$P_POSTGRES_PASSWORD"
export P_POSTGRES_HOST="$P_POSTGRES_HOST"
export P_POSTGRES_PORT="$P_POSTGRES_PORT"

# Redis
export P_REDIS_URL="$P_REDIS_URL"

# DigitalOcean Spaces
export P_USE_SPACES="$P_USE_SPACES"
export P_SPACES_ACCESS_KEY_ID="$P_SPACES_ACCESS_KEY_ID"
export P_SPACES_SECRET_ACCESS_KEY="$P_SPACES_SECRET_ACCESS_KEY"
export P_SPACES_BUCKET_NAME="$P_SPACES_BUCKET_NAME"
export P_SPACES_ENDPOINT_URL="$P_SPACES_ENDPOINT_URL"
export P_SPACES_REGION="$P_SPACES_REGION"
export P_SPACES_CDN_DOMAIN="$P_SPACES_CDN_DOMAIN"

# Django
export SECRET_KEY="$SECRET_KEY"
export ALLOWED_HOSTS="$ALLOWED_HOSTS"
export P_CORS_ALLOWED_ORIGINS="$P_CORS_ALLOWED_ORIGINS"

# Cargar variables: source .env.production
EOF

    chmod 600 .env.production
    log_success "Archivo .env.production creado (permisos 600 para seguridad)"
}

# Verificar si ya existen variables de entorno
if [ -f ".env.production" ]; then
    log_info "Archivo .env.production encontrado"
    echo -n "¿Quieres cargar las variables existentes? (y/N): "
    read load_existing
    if [[ $load_existing =~ ^[Yy]$ ]]; then
        source .env.production
        log_success "Variables cargadas desde .env.production"
    else
        request_env_vars
        save_env_file
    fi
else
    request_env_vars
    save_env_file
fi

# Verificar variables obligatorias
log_info "Verificando variables obligatorias..."

required_vars=("P_POSTGRES_PASSWORD" "P_SPACES_ACCESS_KEY_ID" "P_SPACES_SECRET_ACCESS_KEY" "SECRET_KEY")
missing_vars=()

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -ne 0 ]; then
    log_error "Faltan las siguientes variables obligatorias:"
    for var in "${missing_vars[@]}"; do
        echo "  - $var"
    done
    exit 1
fi

log_success "Todas las variables obligatorias están configuradas"

# Crear directorios necesarios
log_info "Creando directorios necesarios..."
mkdir -p logs ssl
log_success "Directorios creados"

# Generar certificados SSL si no existen
if [ ! -f "ssl/fruitpos.crt" ] || [ ! -f "ssl/fruitpos.key" ]; then
    log_info "Generando certificados SSL..."
    if [ -f "scripts/generate-ssl-certs.sh" ]; then
        chmod +x scripts/generate-ssl-certs.sh
        ./scripts/generate-ssl-certs.sh
    else
        log_warning "Script de certificados no encontrado, generando manualmente..."
        openssl genrsa -out ssl/fruitpos.key 2048
        openssl req -new -x509 -key ssl/fruitpos.key -out ssl/fruitpos.crt -days 365 \
            -subj "/C=CL/ST=Santiago/L=Santiago/O=FruitPOS/OU=IT/CN=fruitpos.cl/emailAddress=admin@fruitpos.cl" \
            -addext "subjectAltName=DNS:fruitpos.cl,DNS:www.fruitpos.cl,DNS:api.fruitpos.cl,DNS:localhost"
        chmod 600 ssl/fruitpos.key
        chmod 644 ssl/fruitpos.crt
    fi
    log_success "Certificados SSL generados"
else
    log_success "Certificados SSL ya existen"
fi

# Detener servicios existentes
log_info "Deteniendo servicios existentes (si existen)..."
docker-compose -f docker-compose.production.yml down --remove-orphans 2>/dev/null || true
log_success "Servicios detenidos"

# Construir imágenes
log_info "Construyendo imágenes Docker..."
docker-compose -f docker-compose.production.yml build --no-cache
log_success "Imágenes construidas"

# Iniciar servicios de base de datos
log_info "Iniciando servicios de base de datos..."
docker-compose -f docker-compose.production.yml up -d db redis
log_success "Base de datos y Redis iniciados"

# Esperar a que la base de datos esté lista
log_info "Esperando a que la base de datos esté lista..."
sleep 15

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
    print('✅ Superusuario creado: admin@fruitpos.cl / admin123')
else:
    print('✅ Superusuario ya existe')
" 2>/dev/null || log_warning "No se pudo verificar/crear superusuario"

# Subir archivos estáticos a Spaces
log_info "Subiendo archivos estáticos a DigitalOcean Spaces..."
docker-compose -f docker-compose.production.yml run --rm --profile tools collectstatic
log_success "Archivos estáticos subidos a Spaces"

# Ejecutar seeds si existen
if [ -f "scripts/run_seeds.py" ]; then
    log_info "Ejecutando seeds de datos iniciales..."
    docker-compose -f docker-compose.production.yml run --rm api python scripts/run_seeds.py 2>/dev/null || log_warning "Seeds no ejecutados (puede ser normal)"
fi

# Iniciar todos los servicios
log_info "Iniciando todos los servicios..."
docker-compose -f docker-compose.production.yml up -d
log_success "Todos los servicios iniciados"

# Esperar a que los servicios estén listos
log_info "Esperando a que los servicios estén completamente listos..."
sleep 20

# Verificar estado de los servicios
log_info "Verificando estado de los servicios..."
docker-compose -f docker-compose.production.yml ps

# Verificar conectividad
log_info "Verificando conectividad..."

# Verificar API local
if curl -f -s http://localhost/api/v1/ > /dev/null 2>&1; then
    log_success "API responde correctamente en HTTP"
else
    log_warning "API no responde en HTTP (puede ser normal si solo HTTPS está habilitado)"
fi

# Verificar HTTPS local
if curl -f -s -k https://localhost/ > /dev/null 2>&1; then
    log_success "HTTPS responde correctamente"
else
    log_warning "HTTPS no responde (verifica certificados)"
fi

# Mostrar información final
echo ""
echo "🎉 ¡Despliegue completado exitosamente!"
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    📋 INFORMACIÓN DE DESPLIEGUE              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "🌐 URLs de tu aplicación:"
echo "  • Frontend:          https://fruitpos.cl"
echo "  • API:               https://fruitpos.cl/api/v1/"
echo "  • Panel Admin:       https://fruitpos.cl/admin/"
echo ""
echo "📦 DigitalOcean Spaces:"
echo "  • Bucket:            $P_SPACES_BUCKET_NAME"
echo "  • Región:            $P_SPACES_REGION"
echo "  • CDN:               https://$P_SPACES_CDN_DOMAIN"
echo "  • Archivos estáticos: https://$P_SPACES_CDN_DOMAIN/fruitpos/static/"
echo "  • Archivos media:    https://$P_SPACES_CDN_DOMAIN/fruitpos/media/"
echo ""
echo "👤 Credenciales de administrador:"
echo "  • Email:             admin@fruitpos.cl"
echo "  • Password:          admin123"
echo "  • ⚠️  IMPORTANTE:     Cambiar password en producción"
echo ""
echo "🔧 Comandos útiles:"
echo "  • Ver logs:          docker-compose -f docker-compose.production.yml logs -f"
echo "  • Reiniciar:         docker-compose -f docker-compose.production.yml restart"
echo "  • Detener:           docker-compose -f docker-compose.production.yml down"
echo "  • Estado:            docker-compose -f docker-compose.production.yml ps"
echo ""
echo "📁 Archivos importantes:"
echo "  • Variables:         .env.production"
echo "  • Logs:              ./logs/"
echo "  • Certificados SSL:  ./ssl/"
echo ""
echo "🔒 Seguridad:"
echo "  • Archivo .env.production tiene permisos 600 (solo propietario puede leer)"
echo "  • Certificados SSL generados (considera usar Let's Encrypt para producción)"
echo "  • Cambiar password de admin en: https://fruitpos.cl/admin/"
echo ""

# Mostrar logs en tiempo real (opcional)
echo -n "¿Quieres ver los logs en tiempo real? (y/N): "
read show_logs
if [[ $show_logs =~ ^[Yy]$ ]]; then
    echo ""
    log_info "Mostrando logs en tiempo real (Ctrl+C para salir)..."
    docker-compose -f docker-compose.production.yml logs -f
fi

log_success "¡FruitPOS está listo para producción en DigitalOcean! 🚀"
