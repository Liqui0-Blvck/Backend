# 🚀 Despliegue Rápido en DigitalOcean

## ⚡ Método Súper Rápido (5 minutos)

### 1. Conectar a tu servidor
```bash
ssh root@tu-servidor-ip
# o si tienes dominio configurado:
ssh root@fruitpos.cl
```

### 2. Clonar y desplegar en un comando
```bash
# Opción A: Desde GitHub (recomendado)
git clone https://github.com/Liqui0-Blvck/Backend.git fruitpos && cd fruitpos && chmod +x scripts/deploy-to-server.sh && ./scripts/deploy-to-server.sh

# Opción B: Si no tienes Git configurado
curl -L https://github.com/Liqui0-Blvck/Backend/archive/main.zip -o fruitpos.zip && unzip fruitpos.zip && mv Backend-main fruitpos && cd fruitpos && chmod +x scripts/deploy-to-server.sh && ./scripts/deploy-to-server.sh
```

### 3. Configurar cuando el script te pregunte:
- **PostgreSQL Password**: Una contraseña segura (ej: `MiFruitPOS2024!`)
- **Spaces Access Key**: Tu access key de DigitalOcean Spaces
- **Spaces Secret Key**: Tu secret key de DigitalOcean Spaces
- **Django Secret**: Presiona Enter para generar automáticamente

¡Listo! El script hace todo automáticamente:
- ✅ Configura variables de entorno
- ✅ Genera certificados SSL
- ✅ Construye imágenes Docker
- ✅ Ejecuta migraciones
- ✅ Sube archivos a Spaces
- ✅ Inicia todos los servicios

---

## 📋 Información que necesitas tener lista:

### Credenciales de DigitalOcean Spaces:
1. Ve a: https://cloud.digitalocean.com/account/api/spaces
2. Crea un nuevo Space Access Key
3. Copia el **Access Key ID** y **Secret Access Key**

### Tu configuración actual:
- **Bucket**: `fruitpost`
- **Región**: `sfo3` (San Francisco)
- **Endpoint**: `https://sfo3.digitaloceanspaces.com`
- **CDN**: `fruitpost.sfo3.cdn.digitaloceanspaces.com`

---

## 🌐 URLs después del despliegue:

- **Frontend**: https://fruitpos.cl
- **API**: https://fruitpos.cl/api/v1/
- **Admin**: https://fruitpos.cl/admin/
- **Credenciales admin**: admin@fruitpos.cl / admin123

---

## 🔧 Comandos útiles después del despliegue:

```bash
# Ver estado de servicios
docker-compose -f docker-compose.production.yml ps

# Ver logs
docker-compose -f docker-compose.production.yml logs -f

# Reiniciar servicios
docker-compose -f docker-compose.production.yml restart

# Detener todo
docker-compose -f docker-compose.production.yml down

# Actualizar código (si haces cambios)
git pull && docker-compose -f docker-compose.production.yml build --no-cache && docker-compose -f docker-compose.production.yml up -d
```

---

## 🚨 Si algo sale mal:

### Verificar logs:
```bash
docker-compose -f docker-compose.production.yml logs api
docker-compose -f docker-compose.production.yml logs nginx
docker-compose -f docker-compose.production.yml logs db
```

### Reiniciar desde cero:
```bash
docker-compose -f docker-compose.production.yml down -v
./scripts/deploy-to-server.sh
```

### Verificar conectividad:
```bash
curl -I http://localhost
curl -I https://localhost
```

---

## 📞 Soporte Rápido:

**Problema**: "Port 80/443 already in use"
```bash
sudo systemctl stop apache2
sudo systemctl stop nginx
```

**Problema**: "Permission denied"
```bash
chmod +x scripts/*.sh
```

**Problema**: "Cannot connect to database"
```bash
docker-compose -f docker-compose.production.yml restart db
```

---

¡Tu FruitPOS estará funcionando en menos de 5 minutos! 🎉
