#!/bin/bash

# ==============================================
# Script para generar certificados SSL para fruitpos.cl
# ==============================================

echo "🔐 Generando certificados SSL para fruitpos.cl..."

# Crear directorio para certificados si no existe
mkdir -p ssl

# Generar clave privada
echo "📝 Generando clave privada..."
openssl genrsa -out ssl/fruitpos.key 2048

# Generar certificado auto-firmado para desarrollo/testing
echo "📜 Generando certificado auto-firmado..."
openssl req -new -x509 -key ssl/fruitpos.key -out ssl/fruitpos.crt -days 365 \
    -subj "/C=CL/ST=Santiago/L=Santiago/O=FruitPOS/OU=IT/CN=fruitpos.cl/emailAddress=admin@fruitpos.cl" \
    -addext "subjectAltName=DNS:fruitpos.cl,DNS:www.fruitpos.cl,DNS:api.fruitpos.cl,DNS:localhost"

# Establecer permisos correctos
echo "🔒 Configurando permisos..."
chmod 600 ssl/fruitpos.key
chmod 644 ssl/fruitpos.crt

echo "✅ Certificados SSL generados exitosamente!"
echo ""
echo "📁 Archivos creados:"
echo "   - ssl/fruitpos.key (clave privada)"
echo "   - ssl/fruitpos.crt (certificado)"
echo ""
echo "⚠️  IMPORTANTE PARA PRODUCCIÓN:"
echo "   - Estos son certificados auto-firmados para desarrollo/testing"
echo "   - Para producción, usa certificados de Let's Encrypt o una CA válida"
echo "   - Comando para Let's Encrypt:"
echo "     certbot certonly --standalone -d fruitpos.cl -d www.fruitpos.cl -d api.fruitpos.cl"
echo ""
echo "🐳 Para usar con Docker:"
echo "   - Los certificados se montarán en /etc/nginx/ssl/ dentro del contenedor"
echo "   - Asegúrate de que el docker-compose.yml tenga el volumen configurado"
