#!/bin/bash
set -e

# Colores para mensajes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configurar explícitamente la variable de entorno para Django
export DJANGO_SETTINGS_MODULE=backend.settings

# Detectar entorno
if [ "$DJANGO_ENV" = "production" ]; then
    echo -e "${GREEN}Ejecutando en modo PRODUCCIÓN${NC}"
    
    # Verificar variables críticas en producción
    if [ -z "$SECRET_KEY" ]; then
        echo -e "${RED}Error: La variable SECRET_KEY no está configurada. Abortando.${NC}"
        exit 1
    fi
    
    if [ "$USE_SPACES" = "True" ] && ([ -z "$P_SPACES_ACCESS_KEY_ID" ] || [ -z "$P_SPACES_SECRET_ACCESS_KEY" ] || [ -z "$P_SPACES_CDN_DOMAIN" ]); then
        echo -e "${RED}Error: Faltan variables de DigitalOcean Spaces. Verifica P_SPACES_ACCESS_KEY_ID, P_SPACES_SECRET_ACCESS_KEY y P_SPACES_CDN_DOMAIN${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}Ejecutando en modo DESARROLLO${NC}"
fi

# Espera a que la base de datos esté lista
echo -e "${YELLOW}Esperando a la base de datos...${NC}"

# Verificar disponibilidad de PostgreSQL con Python (no depende de pg_isready)
while ! python -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.connect((\"${POSTGRES_HOST:-db}\", int(\"${POSTGRES_PORT:-5432}\"))); s.close()" 2>/dev/null; do
    echo -e "${YELLOW}PostgreSQL no está disponible aún - esperando...${NC}"
    sleep 2
done
echo -e "${GREEN}PostgreSQL está disponible!${NC}"
echo -e "${GREEN}¡Base de datos lista!${NC}"

# SALTAMOS LAS MIGRACIONES PORQUE YA LAS APLICAMOS MANUALMENTE
echo -e "${YELLOW}Saltando migraciones (ya aplicadas manualmente)...${NC}"

# Collectstatic (solo en producción o si se solicita explícitamente)
if [ "$DJANGO_ENV" = "production" ] || [ "$COLLECT_STATIC" = "True" ]; then
    echo -e "${YELLOW}Recolectando archivos estáticos...${NC}"
    python manage.py collectstatic --noinput
fi

# Imprimir información de depuración
echo -e "${GREEN}Iniciando servidor con DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE${NC}"
echo -e "${GREEN}Entorno: $DJANGO_ENV${NC}"

# Iniciar Daphne para ambos entornos
echo -e "${GREEN}Iniciando Daphne...${NC}"
exec daphne -b 0.0.0.0 -p 8000 backend.asgi:application
