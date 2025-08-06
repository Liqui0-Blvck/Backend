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

echo -e "${GREEN}=== Transfiriendo archivo .env.production al droplet ===${NC}"

# Verificar que el archivo existe
if [ ! -f .env.production ]; then
    echo -e "${RED}Error: El archivo .env.production no existe${NC}"
    exit 1
fi

# Transferir el archivo
echo -e "${YELLOW}Transfiriendo .env.production...${NC}"
scp .env.production $SSH_USER@$DROPLET_IP:$REMOTE_DIR/

# Verificar que se transfirió correctamente
echo -e "${YELLOW}Verificando que el archivo se transfirió correctamente...${NC}"
ssh $SSH_USER@$DROPLET_IP << 'ENDSSH'
cd /opt/fruitpos
if [ -f .env.production ]; then
    echo "Archivo .env.production transferido correctamente"
    echo "Contenido del archivo:"
    cat .env.production
else
    echo "Error: El archivo .env.production no se transfirió correctamente"
    exit 1
fi
ENDSSH

echo -e "${GREEN}=== Transferencia completada ===${NC}"
echo -e "${YELLOW}Para reiniciar los contenedores, ejecuta:${NC}"
echo -e "${GREEN}ssh $SSH_USER@$DROPLET_IP 'cd $REMOTE_DIR && docker-compose -f docker-compose.production.yml down && docker-compose -f docker-compose.production.yml up -d'${NC}"
