FROM python:3.11-slim

# Variables de entorno para Python
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PYTHONPATH=/app

# Instalar dependencias del sistema necesarias
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Crear usuario no-root para seguridad
RUN groupadd -r django && useradd -r -g django django

# Crear directorios necesarios
RUN mkdir -p /app/static /app/media /app/logs

WORKDIR /app

# Copiar archivos de dependencias
COPY requirements.txt ./
COPY requirements-production.txt ./

# Instalar dependencias base
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Instalar dependencias de producción (incluye django-storages, boto3)
# Esto asegura que DigitalOcean Spaces funcione correctamente
RUN pip install -r requirements-production.txt

# Copiar código de la aplicación
COPY . .

# Copiar y configurar entrypoint
COPY docker-entrypoint-new.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Configurar permisos para usuario django
RUN chown -R django:django /app

# Cambiar a usuario no-root
USER django

# Exponer puerto
EXPOSE 8000

# Comando por defecto
CMD ["/app/docker-entrypoint.sh"]
