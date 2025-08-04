"""
Backends de almacenamiento personalizados para DigitalOcean Spaces
Separa archivos estáticos y media en diferentes ubicaciones del bucket
"""

from storages.backends.s3boto3 import S3Boto3Storage
from django.conf import settings


class StaticStorage(S3Boto3Storage):
    """
    Storage backend para archivos estáticos en DigitalOcean Spaces
    """
    location = f"{settings.AWS_LOCATION}/static"
    default_acl = 'public-read'
    file_overwrite = True  # Los archivos estáticos pueden sobrescribirse
    
    def __init__(self, *args, **kwargs):
        kwargs['custom_domain'] = settings.AWS_S3_CUSTOM_DOMAIN
        super().__init__(*args, **kwargs)


class MediaStorage(S3Boto3Storage):
    """
    Storage backend para archivos media (uploads de usuarios) en DigitalOcean Spaces
    """
    location = f"{settings.AWS_LOCATION}/media"
    default_acl = 'public-read'
    file_overwrite = False  # Los archivos media NO deben sobrescribirse
    
    def __init__(self, *args, **kwargs):
        kwargs['custom_domain'] = settings.AWS_S3_CUSTOM_DOMAIN
        super().__init__(*args, **kwargs)


class PrivateMediaStorage(S3Boto3Storage):
    """
    Storage backend para archivos media privados en DigitalOcean Spaces
    Útil para documentos sensibles que requieren autenticación
    """
    location = f"{settings.AWS_LOCATION}/private"
    default_acl = 'private'
    file_overwrite = False
    querystring_auth = True  # Requiere URLs firmadas para acceso
    
    def __init__(self, *args, **kwargs):
        kwargs['custom_domain'] = None  # No usar CDN para archivos privados
        super().__init__(*args, **kwargs)
