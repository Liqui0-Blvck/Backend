from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.utils import timezone

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import IsAdminOrOwner

from .models import Announcement, AnnouncementConfirmation
from .serializers import AnnouncementSerializer, AnnouncementDetailSerializer, AnnouncementConfirmationSerializer


class AnnouncementViewSet(viewsets.ModelViewSet):
    """ViewSet para ver y editar anuncios"""
    queryset = Announcement.objects.all()
    serializer_class = AnnouncementSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrOwner]
    lookup_field = 'uid'
    
    def get_queryset(self):
        # Filtrar anuncios por negocio del usuario y estado
        user = self.request.user
        queryset = Announcement.objects.filter(business=user.perfil.business)
        
        # Filtrar por tipo si se especifica
        tipo = self.request.query_params.get('tipo', None)
        if tipo:
            queryset = queryset.filter(tipo=tipo)
        
        # Filtrar por estado si se especifica
        estado = self.request.query_params.get('estado', None)
        if estado:
            queryset = queryset.filter(estado=estado)
        else:
            # Por defecto, mostrar solo anuncios activos o programados que ya hayan iniciado
            queryset = queryset.filter(
                Q(estado='activo') | 
                (Q(estado='programado') & Q(fecha_inicio__lte=timezone.now()))
            )
        
        # Filtrar por destacados si se especifica
        destacado = self.request.query_params.get('destacado', None)
        if destacado and destacado.lower() == 'true':
            queryset = queryset.filter(destacado=True)
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return AnnouncementDetailSerializer
        return AnnouncementSerializer
    
    def perform_create(self, serializer):
        # Asignar automáticamente el usuario actual como creador
        serializer.save(creador=self.request.user)
    
    @action(detail=True, methods=['post'])
    def confirmar(self, request, uid=None):
        """Confirmar la lectura de un anuncio"""
        anuncio = self.get_object()
        usuario = request.user
        
        # Verificar si ya existe una confirmación
        confirmacion, created = AnnouncementConfirmation.objects.get_or_create(
            announcement=anuncio,
            usuario=usuario,
            defaults={'comentario': request.data.get('comentario', '')}
        )
        
        if not created and 'comentario' in request.data:
            # Actualizar comentario si ya existe la confirmación
            confirmacion.comentario = request.data.get('comentario')
            confirmacion.save()
        
        serializer = AnnouncementConfirmationSerializer(confirmacion)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def mis_pendientes(self, request):
        """Obtener anuncios activos que requieren confirmación y no han sido confirmados por el usuario"""
        usuario = request.user
        
        # Obtener IDs de anuncios ya confirmados por el usuario
        confirmados_ids = AnnouncementConfirmation.objects.filter(usuario=usuario).values_list('announcement_id', flat=True)
        
        # Filtrar anuncios activos que requieren confirmación y no han sido confirmados
        queryset = self.get_queryset().filter(
            requiere_confirmacion=True,
            estado='activo'
        ).exclude(id__in=confirmados_ids)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
