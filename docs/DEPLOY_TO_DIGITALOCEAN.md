# Despliegue de FruitPOS en DigitalOcean

## 📋 Guía Completa de Despliegue

Esta guía te ayudará a desplegar tu proyecto FruitPOS en tu servidor de DigitalOcean paso a paso.

## 🔧 Prerrequisitos

### En tu Servidor DigitalOcean:
- ✅ Docker instalado
- ✅ Docker Compose instalado
- ✅ Git instalado
- ✅ Acceso SSH al servidor
- ✅ Dominio fruitpos.cl apuntando al servidor

### Credenciales que necesitas:
- ✅ Access Key ID de DigitalOcean Spaces
- ✅ Secret Access Key de DigitalOcean Spaces
- ✅ Contraseña segura para PostgreSQL
- ✅ Secret Key para Django

## 🚀 Método 1: Despliegue Automatizado (Recomendado)

### Paso 1: Conectar al servidor
```bash
ssh root@tu-servidor-ip
# o
ssh tu-usuario@fruitpos.cl
```

### Paso 2: Clonar el repositorio
```bash
# Clonar desde GitHub
git clone https://github.com/Liqui0-Blvck/Backend.git fruitpos-backend
cd fruitpos-backend

# O si prefieres usar HTTPS
git clone https://github.com/Liqui0-Blvck/Backend.git fruitpos-backend
cd fruitpos-backend
```

### Paso 3: Configurar variables de entorno
```bash
# Crear archivo de variables de entorno
nano .env.production

# Agregar estas variables (CAMBIAR VALORES REALES):
export P_POSTGRES_PASSWORD="TU_PASSWORD_SUPER_SEGURO"
export P_SPACES_ACCESS_KEY_ID="tu_spaces_access_key_real"
export P_SPACES_SECRET_ACCESS_KEY="tu_spaces_secret_key_real"
export SECRET_KEY="tu_django_secret_key_super_largo_y_seguro"

# Opcional - personalizar otros valores:
# export P_POSTGRES_DB="fruitpos_prod"
# export P_POSTGRES_USER="fruitpos_user"
# export ALLOWED_HOSTS="fruitpos.cl,www.fruitpos.cl,api.fruitpos.cl"
```

### Paso 4: Cargar variables y ejecutar despliegue
```bash
# Cargar variables de entorno
source .env.production

# Ejecutar script de despliegue automatizado
chmod +x scripts/deploy-with-spaces.sh
./scripts/deploy-with-spaces.sh
```

¡Listo! El script automáticamente:
- ✅ Verificará todas las variables
- ✅ Generará certificados SSL
- ✅ Construirá las imágenes Docker
- ✅ Ejecutará migraciones
- ✅ Subirá archivos estáticos a Spaces
- ✅ Iniciará todos los servicios

## 🔧 Método 2: Despliegue Manual (Paso a Paso)

### Paso 1: Preparar el servidor
```bash
# Conectar al servidor
ssh root@tu-servidor-ip

# Actualizar sistema
apt update && apt upgrade -y

# Verificar Docker
docker --version
docker-compose --version
```

### Paso 2: Clonar y preparar proyecto
```bash
# Clonar repositorio
git clone https://github.com/Liqui0-Blvck/Backend.git fruitpos-backend
cd fruitpos-backend

# Crear directorios necesarios
mkdir -p logs ssl

# Dar permisos a scripts
chmod +x scripts/*.sh
```

### Paso 3: Configurar variables de entorno
```bash
# Crear archivo .env.production
cat > .env.production << 'EOF'
# Variables obligatorias - CAMBIAR POR VALORES REALES
export P_POSTGRES_PASSWORD="TU_PASSWORD_SUPER_SEGURO"
export P_SPACES_ACCESS_KEY_ID="tu_spaces_access_key_real"
export P_SPACES_SECRET_ACCESS_KEY="tu_spaces_secret_key_real"
export SECRET_KEY="tu_django_secret_key_super_largo_y_seguro"

# Variables opcionales (ya tienen valores por defecto)
export P_POSTGRES_DB="fruitpos_prod"
export P_POSTGRES_USER="fruitpos_user"
export P_POSTGRES_HOST="db"
export P_POSTGRES_PORT="5432"
export P_REDIS_URL="redis://redis:6379/0"
export P_USE_SPACES="True"
export P_SPACES_BUCKET_NAME="fruitpost"
export P_SPACES_ENDPOINT_URL="https://sfo3.digitaloceanspaces.com"
export P_SPACES_REGION="sfo3"
export P_SPACES_CDN_DOMAIN="fruitpost.sfo3.cdn.digitaloceanspaces.com"
export ALLOWED_HOSTS="fruitpos.cl,www.fruitpos.cl,api.fruitpos.cl"
export P_CORS_ALLOWED_ORIGINS="https://fruitpos.cl,https://www.fruitpos.cl"
EOF

# Cargar variables
source .env.production
```

### Paso 4: Generar certificados SSL
```bash
# Generar certificados SSL
./scripts/generate-ssl-certs.sh

# O usar Let's Encrypt (recomendado para producción)
# Instalar certbot primero:
# apt install certbot
# certbot certonly --standalone -d fruitpos.cl -d www.fruitpos.cl -d api.fruitpos.cl
# cp /etc/letsencrypt/live/fruitpos.cl/fullchain.pem ssl/fruitpos.crt
# cp /etc/letsencrypt/live/fruitpos.cl/privkey.pem ssl/fruitpos.key
```

### Paso 5: Construir y ejecutar
```bash
# Construir imágenes
docker-compose -f docker-compose.production.yml build --no-cache

# Iniciar base de datos
docker-compose -f docker-compose.production.yml up -d db redis

# Esperar a que la base de datos esté lista
sleep 15

# Ejecutar migraciones
docker-compose -f docker-compose.production.yml run --rm api python manage.py migrate

# Crear superusuario
docker-compose -f docker-compose.production.yml run --rm api python manage.py createsuperuser

# Subir archivos estáticos a Spaces
docker-compose -f docker-compose.production.yml run --rm --profile tools collectstatic

# Ejecutar seeds (opcional)
docker-compose -f docker-compose.production.yml run --rm api python scripts/run_seeds.py

# Iniciar todos los servicios
docker-compose -f docker-compose.production.yml up -d

# Ver logs
docker-compose -f docker-compose.production.yml logs -f
```

## 📁 Método 3: Transferir Archivos Locales (Si no usas Git)

### Opción A: Usar SCP
```bash
# Desde tu máquina local, comprimir proyecto
cd /Users/nicolascortes/Desktop/proyectos/fruitpos/
tar -czf fruitpos-backend.tar.gz Backend/

# Transferir al servidor
scp fruitpos-backend.tar.gz root@tu-servidor-ip:/root/

# En el servidor, extraer
ssh root@tu-servidor-ip
cd /root
tar -xzf fruitpos-backend.tar.gz
mv Backend fruitpos-backend
cd fruitpos-backend
```

### Opción B: Usar rsync
```bash
# Desde tu máquina local
rsync -avz --exclude='node_modules' --exclude='.git' --exclude='__pycache__' \
  /Users/nicolascortes/Desktop/proyectos/fruitpos/Backend/ \
  root@tu-servidor-ip:/root/fruitpos-backend/
```

## 🔍 Verificación del Despliegue

### Verificar servicios
```bash
# Ver estado de contenedores
docker-compose -f docker-compose.production.yml ps

# Ver logs
docker-compose -f docker-compose.production.yml logs api
docker-compose -f docker-compose.production.yml logs nginx

# Verificar conectividad
curl -I http://localhost
curl -I https://localhost
```

### Verificar URLs
```bash
# API
curl https://fruitpos.cl/api/v1/

# Admin
curl https://fruitpos.cl/admin/

# Archivos estáticos desde Spaces
curl -I https://fruitpost.sfo3.cdn.digitaloceanspaces.com/fruitpos/static/admin/css/base.css
```

## 🔧 Comandos Útiles de Mantenimiento

### Gestión de servicios
```bash
# Ver logs en tiempo real
docker-compose -f docker-compose.production.yml logs -f

# Reiniciar servicios
docker-compose -f docker-compose.production.yml restart

# Detener servicios
docker-compose -f docker-compose.production.yml down

# Actualizar código (si usas Git)
git pull origin main
docker-compose -f docker-compose.production.yml build --no-cache
docker-compose -f docker-compose.production.yml up -d
```

### Backup de base de datos
```bash
# Crear backup
docker-compose -f docker-compose.production.yml exec db pg_dump -U fruitpos_user fruitpos_prod > backup_$(date +%Y%m%d_%H%M%S).sql

# Restaurar backup
docker-compose -f docker-compose.production.yml exec -T db psql -U fruitpos_user fruitpos_prod < backup.sql
```

### Actualizar archivos estáticos
```bash
# Subir nuevos archivos estáticos a Spaces
docker-compose -f docker-compose.production.yml run --rm --profile tools collectstatic
```

## 🚨 Troubleshooting

### Problema: "Port already in use"
```bash
# Ver qué proceso usa el puerto
sudo lsof -i :80
sudo lsof -i :443

# Detener proceso si es necesario
sudo systemctl stop apache2  # Si Apache está corriendo
sudo systemctl stop nginx    # Si Nginx está corriendo
```

### Problema: "Permission denied"
```bash
# Dar permisos a archivos
chmod +x scripts/*.sh
chown -R $USER:$USER .
```

### Problema: "Cannot connect to database"
```bash
# Verificar que la base de datos esté corriendo
docker-compose -f docker-compose.production.yml logs db

# Reiniciar base de datos
docker-compose -f docker-compose.production.yml restart db
```

### Problema: "SSL certificate error"
```bash
# Regenerar certificados
./scripts/generate-ssl-certs.sh

# O usar Let's Encrypt
certbot renew
```

## 🔒 Configuración de Firewall (Opcional)

```bash
# Configurar UFW
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

## 📊 Monitoreo

### Ver recursos del sistema
```bash
# Uso de Docker
docker stats

# Espacio en disco
df -h

# Memoria
free -h

# Procesos
htop
```

## 🎯 URLs Finales

Una vez desplegado, tu aplicación estará disponible en:

- **Frontend**: https://fruitpos.cl
- **API**: https://fruitpos.cl/api/v1/
- **Admin**: https://fruitpos.cl/admin/
- **Archivos estáticos**: https://fruitpost.sfo3.cdn.digitaloceanspaces.com/fruitpos/static/
- **Archivos media**: https://fruitpost.sfo3.cdn.digitaloceanspaces.com/fruitpos/media/

## 📞 Soporte

Si tienes problemas durante el despliegue:

1. Revisa los logs: `docker-compose -f docker-compose.production.yml logs`
2. Verifica las variables de entorno
3. Asegúrate de que el dominio apunte al servidor
4. Verifica que los puertos 80 y 443 estén abiertos

---

**¡Tu aplicación FruitPOS estará lista para producción!** 🚀
