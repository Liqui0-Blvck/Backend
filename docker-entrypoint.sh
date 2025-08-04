#!/bin/bash
set -e

# Configurar explícitamente la variable de entorno para Django
export DJANGO_SETTINGS_MODULE=backend.settings

# Espera a que la base de datos esté lista
if [ "$DJANGO_ENV" = "production" ]; then
  echo "Esperando a la base de datos..."
  until pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER"; do
    sleep 1
  done
fi

# Migraciones y collectstatic
python manage.py migrate --noinput
python manage.py collectstatic --noinput

# Imprimir información de depuración
echo "Iniciando servidor con DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE"

# Ejecutar el comando proporcionado
exec "$@"
