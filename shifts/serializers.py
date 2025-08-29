from rest_framework import serializers
from django.db.models import Sum
from django.utils import timezone
from .models import Shift, BoxRefill, ShiftExpense, ShiftClosing
from sales.models import Sale, SaleItem

class ShiftSerializer(serializers.ModelSerializer):
    usuario_abre_nombre = serializers.SerializerMethodField()
    usuario_cierra_nombre = serializers.SerializerMethodField()
    duracion_minutos = serializers.SerializerMethodField()
    
    class Meta:
        model = Shift
        fields = '__all__'
    
    def get_usuario_abre_nombre(self, obj):
        if obj.usuario_abre:
            return f"{obj.usuario_abre.first_name} {obj.usuario_abre.last_name}".strip() or obj.usuario_abre.username
        return None
    
    def get_usuario_cierra_nombre(self, obj):
        if obj.usuario_cierra:
            return f"{obj.usuario_cierra.first_name} {obj.usuario_cierra.last_name}".strip() or obj.usuario_cierra.username
        return None
    
    def get_duracion_minutos(self, obj):
        if obj.fecha_apertura and obj.fecha_cierre:
            # Calcular la duración en minutos
            delta = obj.fecha_cierre - obj.fecha_apertura
            return int(delta.total_seconds() / 60)
        return None


class ShiftClosingSerializer(serializers.ModelSerializer):
    """Serializador para el cierre de caja del turno"""
    cerrado_por_nombre = serializers.SerializerMethodField()
    # Aceptar UID del turno en creación/actualización
    shift = serializers.CharField(write_only=True, required=True)
    # Exponer el UID del turno en respuestas
    shift_uid = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ShiftClosing
        fields = [
            'id', 'shift', 'shift_uid', 'business', 'fecha_cierre_caja', 'cerrado_por', 'cerrado_por_nombre',
            'efectivo_declarado', 'cajas_contadas', 'cajas_vacias_total', 'bins_total',
            'cajas_vacias_toros', 'cajas_vacias_plasticos',
            'notas', 'explicacion_diferencias'
        ]

    def get_cerrado_por_nombre(self, obj):
        if obj.cerrado_por:
            return f"{obj.cerrado_por.first_name} {obj.cerrado_por.last_name}".strip() or obj.cerrado_por.username
        return None

    def get_shift_uid(self, obj):
        try:
            return str(obj.shift.uid) if getattr(obj, 'shift', None) else None
        except Exception:
            return None

    def validate(self, attrs):
        """
        Reglas de validación de cierre de caja:
        - Se valida la diferencia en efectivo (ventas_efectivo - gastos_efectivo vs efectivo_declarado).
        - Se valida la diferencia de cajas (cajas_vendidas vs cajas_contadas).
        - Validaciones de conteo de cajas vacías: no negativos y toros+plásticos <= total.
        - Validación de bins_total: no negativo.
        - Si hay diferencias, se exige 'explicacion_diferencias'.
        """
        # Obtener turno
        if self.instance:
            shift = self.instance.shift
        else:
            shift_uid = (self.initial_data or {}).get('shift')
            if not shift_uid:
                raise serializers.ValidationError({'shift': 'Es obligatorio especificar el turno.'})
            try:
                shift = Shift.objects.get(uid=shift_uid)
            except Shift.DoesNotExist:
                raise serializers.ValidationError({'shift': 'Turno no encontrado.'})

        fecha_inicio = shift.fecha_apertura
        fecha_fin = shift.fecha_cierre or timezone.now()

        # Calcular ventas en efectivo del turno
        ventas_qs = Sale.objects.filter(
            business=shift.business,
            created_at__gte=fecha_inicio,
            created_at__lte=fecha_fin,
            metodo_pago='efectivo'
        )
        ventas_efectivo = float(ventas_qs.aggregate(total=Sum('total'))['total'] or 0)

        # Calcular gastos en efectivo del turno
        gastos_qs = ShiftExpense.objects.filter(shift=shift, metodo_pago='efectivo')
        gastos_efectivo = float(gastos_qs.aggregate(total=Sum('monto'))['total'] or 0)

        esperado_efectivo = ventas_efectivo - gastos_efectivo

        efectivo_declarado = float(attrs.get('efectivo_declarado', getattr(self.instance, 'efectivo_declarado', 0) or 0))

        # Cajas esperadas en inventario al cierre (stock actual)
        from inventory.models import FruitLot
        cajas_esperadas = int(
            FruitLot.objects.filter(business=shift.business, cantidad_cajas__gt=0)
            .aggregate(total=Sum('cantidad_cajas'))['total'] or 0
        )
        cajas_contadas = int(attrs.get('cajas_contadas', getattr(self.instance, 'cajas_contadas', 0) or 0))

        # Validaciones adicionales de conteos declarados
        cajas_vacias_total = int(attrs.get('cajas_vacias_total', getattr(self.instance, 'cajas_vacias_total', 0) or 0))
        cajas_vacias_toros = int(attrs.get('cajas_vacias_toros', getattr(self.instance, 'cajas_vacias_toros', 0) or 0))
        cajas_vacias_plasticos = int(attrs.get('cajas_vacias_plasticos', getattr(self.instance, 'cajas_vacias_plasticos', 0) or 0))
        bins_total = int(attrs.get('bins_total', getattr(self.instance, 'bins_total', 0) or 0))

        errores_conteos = {}
        if cajas_vacias_total < 0 or cajas_vacias_toros < 0 or cajas_vacias_plasticos < 0:
            errores_conteos['cajas_vacias'] = 'Los conteos de cajas vacías no pueden ser negativos.'
        if bins_total < 0:
            errores_conteos['bins_total'] = 'Los bins contados no pueden ser negativos.'
        if cajas_vacias_toros + cajas_vacias_plasticos > cajas_vacias_total:
            errores_conteos['cajas_vacias_suma'] = 'La suma de toros y plásticos no puede exceder el total de cajas vacías.'
        if errores_conteos:
            raise serializers.ValidationError(errores_conteos)

        # Tolerancias
        TOLERANCIA_EFECTIVO = 1.0  # $1
        # Para cajas, cualquier diferencia requiere explicación

        diff_efectivo = efectivo_declarado - esperado_efectivo
        diff_cajas = cajas_contadas - cajas_esperadas

        requiere_explicacion = abs(diff_efectivo) > TOLERANCIA_EFECTIVO or diff_cajas != 0

        explicacion = attrs.get('explicacion_diferencias', getattr(self.instance, 'explicacion_diferencias', '') or '')
        if requiere_explicacion and not str(explicacion).strip():
            raise serializers.ValidationError({
                'explicacion_diferencias': 'Se requiere una explicación cuando hay diferencias de efectivo o de cajas.',
                'detalle_diferencias': {
                    'efectivo_esperado': esperado_efectivo,
                    'efectivo_declarado': efectivo_declarado,
                    'diferencia_efectivo': diff_efectivo,
                    'cajas_esperadas': cajas_esperadas,
                    'cajas_contadas': cajas_contadas,
                    'diferencia_cajas': diff_cajas,
                }
            })

        return attrs


class ShiftExpenseSerializer(serializers.ModelSerializer):
    """Serializador para los gastos incurridos durante un turno"""
    autorizado_por_nombre = serializers.SerializerMethodField()
    registrado_por_nombre = serializers.SerializerMethodField()
    categoria_display = serializers.SerializerMethodField()
    metodo_pago_display = serializers.SerializerMethodField()
    comprobante_url = serializers.SerializerMethodField()
    
    class Meta:
        model = ShiftExpense
        fields = [
            'id', 'shift', 'descripcion', 'monto', 'categoria', 'categoria_display',
            'metodo_pago', 'metodo_pago_display', 'comprobante', 'comprobante_url',
            'numero_comprobante', 'autorizado_por', 'autorizado_por_nombre',
            'registrado_por', 'registrado_por_nombre', 'fecha', 'notas', 'business'
        ]
    
    def get_autorizado_por_nombre(self, obj):
        if obj.autorizado_por:
            return f"{obj.autorizado_por.first_name} {obj.autorizado_por.last_name}".strip() or obj.autorizado_por.username
        return None
    
    def get_registrado_por_nombre(self, obj):
        if obj.registrado_por:
            return f"{obj.registrado_por.first_name} {obj.registrado_por.last_name}".strip() or obj.registrado_por.username
        return None
    
    def get_categoria_display(self, obj):
        return obj.get_categoria_display()
    
    def get_metodo_pago_display(self, obj):
        return obj.get_metodo_pago_display()
    
    def get_comprobante_url(self, obj):
        if obj.comprobante:
            return obj.comprobante.url
        return None


class ShiftEstadoSerializer(serializers.Serializer):
    """Serializador para el endpoint estado de turnos.
    Devuelve sólo:
    - estado: 'activo' | 'desactivado'
    - cantidad_cajas_inventario: int
    - dinero_en_efectivo: float (ventas efectivo - gastos efectivo en el turno activo)
    """
    estado = serializers.SerializerMethodField()
    cantidad_cajas_inventario = serializers.SerializerMethodField()
    dinero_en_efectivo = serializers.SerializerMethodField()
    usuario_id = serializers.SerializerMethodField()
    turno_uid = serializers.SerializerMethodField()

    def to_representation(self, obj):
        """Ensure serializer returns data even when instance is None."""
        data = {
            'estado': self.get_estado(obj),
            'cantidad_cajas_inventario': self.get_cantidad_cajas_inventario(obj),
            'dinero_en_efectivo': self.get_dinero_en_efectivo(obj),
            'usuario_id': self.get_usuario_id(obj),
            'turno_uid': self.get_turno_uid(obj),
        }
        # Agregar SIEMPRE info de cajas vacías/bins desde inventario (con 0 por defecto)
        data['cajas_vacias_total'] = 0
        data['cajas_vacias_toros'] = 0
        data['cajas_vacias_plasticos'] = 0
        data['bins_total'] = 0
        try:
            from inventory.models import BoxType, FruitBin
            business = self._get_business()
            # Cajas vacías
            qs = BoxType.objects.filter(business=business)
            total_vacias = int(qs.aggregate(total=Sum('stock_cajas_vacias'))['total'] or 0)
            data['cajas_vacias_total'] = total_vacias
            # Desglose por nombre estándar
            toros = int(qs.filter(nombre='toro').aggregate(total=Sum('stock_cajas_vacias'))['total'] or 0)
            plasticos = int(qs.filter(nombre='plastico').aggregate(total=Sum('stock_cajas_vacias'))['total'] or 0)
            data['cajas_vacias_toros'] = toros
            data['cajas_vacias_plasticos'] = plasticos
            # Bins
            bins_total = int(FruitBin.objects.filter(business=business).count())
            data['bins_total'] = bins_total
        except Exception:
            # No romper el endpoint de estado por errores de lectura
            pass
        return data

    def _get_business(self):
        business = self.context.get('business')
        if business is None:
            raise RuntimeError('ShiftEstadoSerializer requiere business en context')
        return business

    def _get_user(self):
        user = self.context.get('user')
        if user is None:
            raise RuntimeError('ShiftEstadoSerializer requiere user en context')
        return user

    def _get_turno_activo(self):
        business = self._get_business()
        return Shift.objects.filter(business=business, estado='abierto').first()

    def get_estado(self, obj):
        return 'activo' if self._get_turno_activo() else 'desactivado'

    def get_cantidad_cajas_inventario(self, obj):
        # Evitar importar aquí para ciclos; import local
        from inventory.models import FruitLot
        business = self._get_business()
        total = FruitLot.objects.filter(business=business, cantidad_cajas__gt=0).aggregate(total=Sum('cantidad_cajas'))['total'] or 0
        try:
            return int(total)
        except Exception:
            return 0

    def get_dinero_en_efectivo(self, obj):
        business = self._get_business()
        turno_activo = self._get_turno_activo()
        if not turno_activo:
            return 0.0
        ventas_efectivo = (
            Sale.objects.filter(
                business=business,
                cancelada=False,
                metodo_pago='efectivo',
                created_at__gte=turno_activo.fecha_apertura,
                created_at__lte=timezone.now(),
            ).aggregate(total=Sum('total'))['total'] or 0
        )
        gastos_efectivo = (
            ShiftExpense.objects.filter(
                shift=turno_activo,
                metodo_pago='efectivo',
            ).aggregate(total=Sum('monto'))['total'] or 0
        )
        try:
            return float(ventas_efectivo) - float(gastos_efectivo)
        except Exception:
            return 0.0

    def get_usuario_id(self, obj):
        user = self._get_user()
        return user.id if user else None

    def get_turno_uid(self, obj):
        turno = self._get_turno_activo()
        return str(turno.uid) if turno and getattr(turno, 'uid', None) else None
