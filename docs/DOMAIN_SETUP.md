# Configuración de Dominio fruitpos.cl

## 📋 Resumen

Esta documentación explica cómo configurar el dominio `fruitpos.cl` para funcionar con tu aplicación FruitPOS tanto en desarrollo como en producción.

## 🔧 Configuración Implementada

### 1. **Nginx Configurado**
- ✅ **Desarrollo**: Puerto 8000 (HTTP) para localhost
- ✅ **Producción**: Puertos 80 (HTTP → HTTPS redirect) y 443 (HTTPS)
- ✅ **Dominios soportados**: `fruitpos.cl`, `www.fruitpos.cl`, `api.fruitpos.cl`
- ✅ **SSL/TLS**: Configuración moderna y segura
- ✅ **Rate limiting**: Protección contra ataques
- ✅ **Headers de seguridad**: HSTS, CSP, etc.

### 2. **Certificados SSL**
- ✅ **Auto-generados**: Certificados para desarrollo/testing
- ✅ **Ubicación**: `ssl/fruitpos.crt` y `ssl/fruitpos.key`
- ✅ **Permisos**: Configurados correctamente
- ✅ **Docker**: Montados en `/etc/nginx/ssl/`

### 3. **Docker Compose**
- ✅ **Puertos expuestos**: 8000 (dev), 80 (HTTP), 443 (HTTPS)
- ✅ **Volúmenes SSL**: Certificados montados correctamente
- ✅ **Variables de entorno**: Configuradas para Nginx

## 🚀 Cómo Usar

### Para Desarrollo Local

1. **Iniciar servicios**:
   ```bash
   docker-compose -f docker-compose.local.yml up -d
   ```

2. **Acceder a la aplicación**:
   - HTTP: `http://localhost:8000`
   - HTTPS: `https://localhost:443` (certificado auto-firmado)

### Para Producción

1. **Configurar DNS**:
   - Apuntar `fruitpos.cl` a la IP de tu servidor
   - Apuntar `www.fruitpos.cl` a la IP de tu servidor
   - Apuntar `api.fruitpos.cl` a la IP de tu servidor

2. **Obtener certificados SSL válidos** (recomendado):
   ```bash
   # Instalar certbot
   sudo apt install certbot python3-certbot-nginx
   
   # Obtener certificados
   sudo certbot certonly --standalone \
     -d fruitpos.cl \
     -d www.fruitpos.cl \
     -d api.fruitpos.cl
   
   # Copiar certificados al directorio ssl/
   sudo cp /etc/letsencrypt/live/fruitpos.cl/fullchain.pem ssl/fruitpos.crt
   sudo cp /etc/letsencrypt/live/fruitpos.cl/privkey.pem ssl/fruitpos.key
   ```

3. **Configurar variables de entorno de producción**:
   ```bash
   # Variables con prefijo P_ para producción
   export P_POSTGRES_DB=fruitpos_prod
   export P_POSTGRES_USER=fruitpos_prod_user
   export P_POSTGRES_PASSWORD=tu-password-seguro
   # ... otras variables P_*
   ```

4. **Iniciar servicios**:
   ```bash
   docker-compose up -d
   ```

## 🔒 Características de Seguridad

### SSL/TLS
- **Protocolos**: TLS 1.2 y 1.3 únicamente
- **Cifrados**: Modernos y seguros
- **HSTS**: Fuerza HTTPS por 1 año
- **OCSP Stapling**: Validación de certificados optimizada

### Headers de Seguridad
- **X-Frame-Options**: Previene clickjacking
- **X-Content-Type-Options**: Previene MIME sniffing
- **Content-Security-Policy**: Política de contenido estricta
- **Referrer-Policy**: Control de referencia

### Rate Limiting
- **API General**: 10 requests/segundo
- **Login/Auth**: 5 requests/minuto
- **Burst**: Permite picos de tráfico controlados

## 🌐 Estructura de URLs

### Desarrollo
- **Frontend**: `http://localhost:5173`
- **API**: `http://localhost:8000/api/v1/`
- **Admin**: `http://localhost:8000/admin/`
- **WebSocket**: `ws://localhost:8000/ws/`

### Producción
- **Frontend**: `https://fruitpos.cl`
- **API**: `https://api.fruitpos.cl/api/v1/`
- **Admin**: `https://api.fruitpos.cl/admin/`
- **WebSocket**: `wss://api.fruitpos.cl/ws/`

## 📁 Archivos Estáticos y Media

### Con DigitalOcean Spaces (Recomendado para Producción)
- **Static**: `https://fruitpos-storage.nyc3.cdn.digitaloceanspaces.com/fruitpos/static/`
- **Media**: `https://fruitpos-storage.nyc3.cdn.digitaloceanspaces.com/fruitpos/media/`

### Sin Spaces (Fallback Local)
- **Static**: `https://fruitpos.cl/static/`
- **Media**: `https://fruitpos.cl/media/`

## 🔧 Troubleshooting

### Problema: "Certificate not trusted"
**Solución**: Los certificados auto-generados no son confiables. Para desarrollo, acepta la excepción en el navegador. Para producción, usa certificados de Let's Encrypt.

### Problema: "Connection refused on port 443"
**Solución**: 
1. Verifica que Docker esté exponiendo el puerto 443
2. Verifica que no haya otro servicio usando el puerto 443
3. Revisa los logs de Nginx: `docker-compose logs nginx`

### Problema: "Rate limit exceeded"
**Solución**: El rate limiting está activo. Espera un momento o ajusta los límites en `nginx.conf` si es necesario.

### Problema: CORS errors
**Solución**: 
1. Para desarrollo: Verifica que el frontend esté en `localhost:5173`
2. Para producción: Configura `P_CORS_ALLOWED_ORIGINS` correctamente

## 📝 Logs y Monitoreo

### Ver logs de Nginx
```bash
docker-compose logs nginx
```

### Ver logs de la API
```bash
docker-compose logs api
```

### Verificar certificados SSL
```bash
openssl x509 -in ssl/fruitpos.crt -text -noout
```

### Probar conectividad HTTPS
```bash
curl -I https://fruitpos.cl
```

## 🔄 Renovación de Certificados

Para certificados de Let's Encrypt, configura renovación automática:

```bash
# Agregar a crontab
0 12 * * * /usr/bin/certbot renew --quiet && docker-compose restart nginx
```

## 📞 Soporte

Si tienes problemas con la configuración del dominio:

1. Revisa los logs de Docker
2. Verifica la configuración DNS
3. Confirma que los puertos estén abiertos en el firewall
4. Verifica que los certificados SSL sean válidos

---

**Última actualización**: 2025-08-04
**Versión**: 1.0
