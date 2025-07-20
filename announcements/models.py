import uuid
from django.db import models
from core.models import BaseModel
from simple_history.models import HistoricalRecords

class Announcement(BaseModel):
    """Modelo para anuncios del administrador a los usuarios del sistema"""
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    TIPO_CHOICES = [
        ('precio', 'Actualización de Precios'),
        ('general', 'Anuncio General'),
        ('urgente', 'Anuncio Urgente'),
        ('promocion', 'Promoción'),
    ]
    
    ESTADO_CHOICES = [
        ('activo', 'Activo'),
        ('inactivo', 'Inactivo'),
        ('programado', 'Programado'),
        ('archivado', 'Archivado'),
    ]
    
    business = models.ForeignKey('business.Business', on_delete=models.CASCADE)
    creador = models.ForeignKey('accounts.CustomUser', on_delete=models.CASCADE, related_name='anuncios_creados')
    titulo = models.CharField(max_length=200)
    contenido = models.TextField()
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='general')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='activo')
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_fin = models.DateTimeField(null=True, blank=True)
    destacado = models.BooleanField(default=False)
    requiere_confirmacion = models.BooleanField(default=False)
    
    history = HistoricalRecords()
    
    def __str__(self):
        return f"{self.titulo} ({self.get_tipo_display()})"
    
    class Meta:
        ordering = ['-fecha_inicio']
        verbose_name = "Anuncio"
        verbose_name_plural = "Anuncios"

class AnnouncementConfirmation(BaseModel):
    """Modelo para registrar las confirmaciones de lectura de los anuncios"""
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name='confirmaciones')
    usuario = models.ForeignKey('accounts.CustomUser', on_delete=models.CASCADE, related_name='anuncios_confirmados')
    fecha_confirmacion = models.DateTimeField(auto_now_add=True)
    comentario = models.TextField(blank=True, null=True)
    
    class Meta:
        unique_together = ('announcement', 'usuario')
        verbose_name = "Confirmación de anuncio"
        verbose_name_plural = "Confirmaciones de anuncios"
    
    def __str__(self):
        return f"{self.usuario.username} confirmó {self.announcement.titulo}"
