from datetime import datetime, time
from decimal import Decimal

from django.db.models import Sum, Count, Q, DecimalField, Value, IntegerField, Case, When, F, CharField
from django.db.models.functions import Coalesce, TruncDate, TruncWeek, TruncMonth
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsSameBusiness
from inventory.models import FruitLot, StockReservation, GoodsReception, SupplierPayment
from sales.models import Sale, SalePending, SaleItem, SalePendingItem
from shifts.models import Shift
from accounts.models import Perfil

# Reusar helper existente
from .views import _get_business_from_user


class DashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated, IsSameBusiness]

    def get(self, request):
        user = request.user
        business = _get_business_from_user(user)
        if not business:
            return Response({"detail": "Usuario no tiene un negocio asociado."}, status=404)

        # Parámetros de filtro
        role_param = request.query_params.get("role")  # opcional, puede forzar rol
        period = request.query_params.get("period", "today")  # today|week|month|custom
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        group_by = request.query_params.get("group_by", "day")  # day|week|month
        include_param = request.query_params.get("include")  # coma-separado
        top_n = int(request.query_params.get("top_n", 5))
        compare = request.query_params.get("compare", "false").lower() == "true"

        # Detectar rol desde grupos (solo: Administrador, Proveedor, Vendedor, Supervisor)
        groups = set(user.groups.values_list('name', flat=True))
        allowed_roles = {"Administrador", "Proveedor", "Vendedor", "Supervisor"}
        # Precedencia: Administrador > Supervisor > Proveedor > Vendedor
        if role_param in allowed_roles:
            role = role_param
        elif 'Administrador' in groups:
            role = 'Administrador'
        elif 'Supervisor' in groups:
            role = 'Supervisor'
        elif 'Proveedor' in groups:
            role = 'Proveedor'
        elif 'Vendedor' in groups:
            role = 'Vendedor'
        else:
            # Si no pertenece a ninguno, tratar como Vendedor por defecto
            role = 'Vendedor'

        # Si es proveedor, obtener proveedor vinculado
        proveedor = None
        if role == 'Proveedor':
            perfil = getattr(user, 'perfil', None)
            proveedor = getattr(perfil, 'proveedor', None)
            if not proveedor:
                try:
                    perfil = Perfil.objects.get(user=user)
                    proveedor = getattr(perfil, 'proveedor', None)
                except Perfil.DoesNotExist:
                    proveedor = None

        # Rango de fecha dinámico
        now = timezone.now()
        hoy = now.date()
        if period == 'today':
            start_dt = datetime.combine(hoy, time.min).replace(tzinfo=now.tzinfo)
            end_dt = datetime.combine(hoy, time.max).replace(tzinfo=now.tzinfo)
        elif period == 'week':
            inicio_semana = hoy - timezone.timedelta(days=hoy.weekday())
            start_dt = datetime.combine(inicio_semana, time.min).replace(tzinfo=now.tzinfo)
            end_dt = datetime.combine(hoy, time.max).replace(tzinfo=now.tzinfo)
        elif period == 'month':
            inicio_mes = hoy.replace(day=1)
            start_dt = datetime.combine(inicio_mes, time.min).replace(tzinfo=now.tzinfo)
            end_dt = datetime.combine(hoy, time.max).replace(tzinfo=now.tzinfo)
        elif period == 'custom' and (date_from or date_to):
            try:
                from django.utils.dateparse import parse_datetime, parse_date
                df = parse_datetime(date_from) if date_from and 'T' in date_from else (parse_date(date_from) if date_from else hoy)
                dt_to = parse_datetime(date_to) if date_to and 'T' in date_to else (parse_date(date_to) if date_to else hoy)
                # Normalizar a datetime con tz
                df = datetime.combine(df, time.min) if isinstance(df, (timezone.datetime,)) and isinstance(df, timezone.datetime) and False else datetime.combine(df, time.min)
                dt_to = datetime.combine(dt_to, time.max) if not isinstance(dt_to, datetime) else dt_to
                start_dt = df.replace(tzinfo=now.tzinfo)
                end_dt = dt_to.replace(tzinfo=now.tzinfo)
            except Exception:
                start_dt = datetime.combine(hoy, time.min).replace(tzinfo=now.tzinfo)
                end_dt = datetime.combine(hoy, time.max).replace(tzinfo=now.tzinfo)
        else:
            start_dt = datetime.combine(hoy, time.min).replace(tzinfo=now.tzinfo)
            end_dt = datetime.combine(hoy, time.max).replace(tzinfo=now.tzinfo)

        # INVENTARIO KPIs
        lotes_qs = FruitLot.objects.filter(business=business).exclude(estado_lote='agotado')
        if role == 'Proveedor' and proveedor:
            lotes_qs = lotes_qs.filter(Q(proveedor=proveedor) | Q(propietario_original=proveedor))

        # Cajas disponibles (para todos los tipos de producto por cajas)
        cajas_disponibles = (
            lotes_qs.aggregate(total=Coalesce(Sum('cantidad_cajas'), 0))['total'] or 0
        )

        # Kg netos disponibles (palta): peso neto - reservas en proceso
        kg_netos_palta = (
            lotes_qs.filter(producto__tipo_producto='palta')
            .aggregate(total=Coalesce(Sum('peso_neto'), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2)))['total'] or Decimal('0')
        )
        kg_reservados_qs = StockReservation.objects.filter(lote__business=business, estado='en_proceso')
        if role == 'Proveedor' and proveedor:
            kg_reservados_qs = kg_reservados_qs.filter(
                Q(lote__proveedor=proveedor) | Q(lote__propietario_original=proveedor)
            )
        kg_reservados = kg_reservados_qs.aggregate(total=Coalesce(Sum('kg_reservados'), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2)))['total'] or Decimal('0')
        kg_netos_disponibles = max(Decimal('0'), Decimal(kg_netos_palta) - Decimal(kg_reservados))

        lotes_activos = lotes_qs.count()
        # Algunos modelos manejan concesión a nivel de lote
        try:
            lotes_concesion = lotes_qs.filter(en_concesion=True).count()
        except Exception:
            lotes_concesion = 0

        inventory_block = {
            "kpis": {
                "cajas_disponibles": int(cajas_disponibles),
                "kg_netos_disponibles": float(kg_netos_disponibles),
                "kg_reservados": float(kg_reservados),
                "lotes_activos": int(lotes_activos),
                "lotes_concesion": int(lotes_concesion),
            }
        }

        # VENTAS HOY
        if role == 'Proveedor' and proveedor:
            # Calcular basado en ítems del proveedor
            items_qs = SaleItem.objects.filter(
                venta__business=business,
                venta__cancelada=False,
                venta__created_at__range=(start_dt, end_dt),
            ).filter(
                Q(lote__proveedor=proveedor) | Q(proveedor_original=proveedor) | Q(lote__propietario_original=proveedor)
            )
            ventas_hoy_count = items_qs.values('venta_id').distinct().count()
            cajas_vendidas_hoy = items_qs.aggregate(
                total=Coalesce(Sum('unidades_vendidas'), 0)
            )['total'] or 0
            total_vendido_hoy = items_qs.aggregate(
                total=Coalesce(Sum('subtotal'), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2))
            )['total'] or Decimal('0')

            pagos_por_metodo = (
                items_qs.values('venta__metodo_pago')
                .annotate(monto=Coalesce(Sum('subtotal'), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2)), ventas=Count('venta_id', distinct=True))
                .order_by()
            )
            pagos_lista = [
                {"metodo": it["venta__metodo_pago"], "monto": float(it["monto"] or 0), "ventas": it["ventas"]}
                for it in pagos_por_metodo
            ]
        else:
            ventas_qs = Sale.objects.filter(business=business, cancelada=False, created_at__range=(start_dt, end_dt))
            ventas_hoy_count = ventas_qs.count()
            cajas_vendidas_hoy = ventas_qs.aggregate(total=Coalesce(Sum('cajas_vendidas'), 0))['total'] or 0
            total_vendido_hoy = ventas_qs.aggregate(total=Coalesce(Sum('total'), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2)))['total'] or Decimal('0')

            pagos_por_metodo = (
                ventas_qs.values('metodo_pago').annotate(monto=Coalesce(Sum('total'), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2)), ventas=Count('id')).order_by()
            )
            pagos_lista = [
                {"metodo": it["metodo_pago"], "monto": float(it["monto"] or 0), "ventas": it["ventas"]}
                for it in pagos_por_metodo
            ]

        if role == 'Proveedor' and proveedor:
            pend_items_qs = SalePendingItem.objects.filter(
                venta_pendiente__business=business,
                venta_pendiente__estado='pendiente',
                venta_pendiente__created_at__range=(start_dt, end_dt),
            ).filter(
                Q(lote__proveedor=proveedor) | Q(lote__propietario_original=proveedor)
            )
            ventas_pendientes = pend_items_qs.values('venta_pendiente_id').distinct().count()
            total_estimado_pend = pend_items_qs.aggregate(total=Coalesce(Sum('subtotal'), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2)))['total'] or Decimal('0')
        else:
            pendientes_qs = SalePending.objects.filter(business=business, estado='pendiente', created_at__range=(start_dt, end_dt))
            ventas_pendientes = pendientes_qs.count()
            total_estimado_pend = pendientes_qs.aggregate(total=Coalesce(Sum('total'), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2)))['total'] or Decimal('0')

        # Enmascarar montos para roles no administrativos (excepto Proveedor por ahora)
        is_admin_like = role in {'Administrador', 'Supervisor'}
        if not is_admin_like and role != 'Proveedor':
            total_vendido_out = None
            pagos_lista_out = [{"metodo": it["metodo"], "monto": None, "ventas": it["ventas"]} for it in pagos_lista]
            total_estimado_pend_out = None
        else:
            total_vendido_out = float(total_vendido_hoy)
            pagos_lista_out = pagos_lista
            total_estimado_pend_out = float(total_estimado_pend)

        ventas_block = {
            "cantidad": ventas_hoy_count,
            "cajas_vendidas": int(cajas_vendidas_hoy),
            "total_vendido": total_vendido_out,
            "por_metodo_pago": pagos_lista_out,
            # Hints para UI
            "ui": {"display": "column"},
            # Dataset para gráfico circular (pie) al lado
            "chart_pie": {
                "title": "Ventas por método de pago",
                "labels": [it["metodo"] for it in pagos_lista_out],
                "values": [
                    (0 if it["monto"] is None else float(it["monto"])) for it in pagos_lista_out
                ],
            },
            "pendientes": {
                "ventas_pendientes": ventas_pendientes,
                "total_estimado": total_estimado_pend_out,
            },
        }

        # RECEPCIONES DEL PROVEEDOR (o generales si no es proveedor)
        recepciones_qs = GoodsReception.objects.filter(
            business=business,
            fecha_recepcion__range=(start_dt, end_dt),
        )
        if role == 'Proveedor' and proveedor:
            recepciones_qs = recepciones_qs.filter(proveedor=proveedor)

        recepciones_count = recepciones_qs.count()
        recepciones_totales = recepciones_qs.aggregate(
            total=Coalesce(Sum('monto_total'), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2))
        )['total'] or Decimal('0')
        recepciones_cajas = recepciones_qs.aggregate(total=Coalesce(Sum('total_cajas'), 0))['total'] or 0
        recepciones_peso_bruto = recepciones_qs.aggregate(
            total=Coalesce(Sum('total_peso_bruto'), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2))
        )['total'] or Decimal('0')
        recepciones_pagadas = recepciones_qs.filter(estado_pago='pagado').count()
        recepciones_pendientes = recepciones_qs.filter(estado_pago='pendiente').count()

        # PAGOS A PROVEEDOR (o generales si no es proveedor)
        pagos_qs = SupplierPayment.objects.filter(
            business=business,
            fecha_pago__range=(start_dt, end_dt),
        )
        if role == 'Proveedor' and proveedor:
            pagos_qs = pagos_qs.filter(recepcion__proveedor=proveedor)

        pagos_count = pagos_qs.count()
        total_pagado = pagos_qs.aggregate(
            total=Coalesce(Sum('monto'), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2))
        )['total'] or Decimal('0')
        pagos_por_metodo_qs = pagos_qs.values('metodo_pago').annotate(
            monto=Coalesce(Sum('monto'), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2)),
            pagos=Count('id')
        ).order_by()
        pagos_por_metodo_lista = [
            {"metodo": it['metodo_pago'], "monto": float(it['monto'] or 0), "pagos": it['pagos']}
            for it in pagos_por_metodo_qs
        ]

        # Saldo por periodo (recepciones - pagos)
        saldo_periodo = Decimal(recepciones_totales) - Decimal(total_pagado)

        # Enmascarar montos para roles no admin ni proveedor
        if not is_admin_like and role != 'Proveedor':
            recepciones_totales_out = None
            recepciones_peso_bruto_out = None
            pagos_total_out = None
            pagos_por_metodo_out = [{"metodo": it["metodo"], "monto": None, "pagos": it["pagos"]} for it in pagos_por_metodo_lista]
            saldo_periodo_out = None
        else:
            recepciones_totales_out = float(recepciones_totales)
            recepciones_peso_bruto_out = float(recepciones_peso_bruto)
            pagos_total_out = float(total_pagado)
            pagos_por_metodo_out = pagos_por_metodo_lista
            saldo_periodo_out = float(saldo_periodo)

        recepciones_block = {
            "cantidad": recepciones_count,
            "monto_total": recepciones_totales_out,
            "total_cajas": int(recepciones_cajas),
            "total_peso_bruto": recepciones_peso_bruto_out,
            "pagadas": recepciones_pagadas,
            "pendientes": recepciones_pendientes,
        }

        pagos_block = {
            "cantidad": pagos_count,
            "monto_total": pagos_total_out,
            "por_metodo": pagos_por_metodo_out,
            "saldo_periodo": saldo_periodo_out,
        }

        # TURNO(S) ACTUAL(ES)
        turnos_block_list = None
        turno_block = {"activo": False}
        if role != 'Proveedor':
            # Admin/Supervisor: ver todos los turnos abiertos del negocio
            if is_admin_like:
                turnos_qs = Shift.objects.filter(business=business, estado='abierto').select_related('usuario_abre')
            else:
                # Vendedor: solo su turno abierto
                turnos_qs = Shift.objects.filter(business=business, estado='abierto', usuario_abre=user).select_related('usuario_abre')

            summaries = []
            for t in turnos_qs:
                # Agregados por related managers
                rellenos_eventos = getattr(t, 'box_refills', None)
                if rellenos_eventos is not None:
                    rellenos_data = rellenos_eventos.aggregate(eventos=Count('id'), cajas_totales=Coalesce(Sum('cantidad_cajas'), 0))
                expenses_mgr = getattr(t, 'expenses', None)
                if expenses_mgr is not None:
                    gastos_total = expenses_mgr.aggregate(
                        monto_total=Coalesce(
                            Sum('monto'),
                            Value(0),
                            output_field=DecimalField(max_digits=12, decimal_places=2),
                        ),
                        cantidad=Count('id'),
                    )
                    gastos_por_categoria_qs = (
                        expenses_mgr.values('categoria')
                        .annotate(
                            monto=Coalesce(
                                Sum('monto'),
                                Value(0),
                                output_field=DecimalField(max_digits=12, decimal_places=2),
                            )
                        )
                        .order_by()
                    )
                    gastos_por_categoria = [
                        {"categoria": it["categoria"], "monto": float(it["monto"] or 0)} for it in gastos_por_categoria_qs
                    ]
                else:
                    gastos_total = {"monto_total": 0, "cantidad": 0}
                    gastos_por_categoria = []

                # Enmascarar montos de gastos para roles no admin (excepto Proveedor por ahora)
                if not is_admin_like and role != 'Proveedor':
                    gastos_total_out = {"monto_total": None, "cantidad": int(gastos_total.get('cantidad') or 0)}
                    gastos_por_categoria_out = [{"categoria": g["categoria"], "monto": None} for g in gastos_por_categoria]
                else:
                    gastos_total_out = {"monto_total": float(gastos_total.get('monto_total') or 0), "cantidad": int(gastos_total.get('cantidad') or 0)}
                    gastos_por_categoria_out = gastos_por_categoria

                summary = {
                    "activo": True,
                    "shift": {
                        "uid": str(t.uid),
                        "usuario_abre": getattr(t.usuario_abre, 'username', ''),
                        "fecha_apertura": t.fecha_apertura,
                        "saldo_inicial": float(t.saldo_inicial or 0),
                    },
                    "operacion": {
                        "rellenos_cajas": {
                            "eventos": int(rellenos_data.get('eventos') or 0),
                            "cajas_totales": int(rellenos_data.get('cajas_totales') or 0),
                        },
                        "gastos": {
                            "cantidad": int(gastos_total_out.get('cantidad') or 0),
                            "monto_total": gastos_total_out.get('monto_total'),
                            "por_categoria": gastos_por_categoria_out,
                        },
                    },
                    # Hints para UI
                    "ui": {"display": "column"},
                    # Dataset para gráfico circular (pie) de gastos por categoría
                    "chart_pie": {
                        "title": "Gastos por categoría",
                        "labels": [g.get("categoria") for g in gastos_por_categoria_out],
                        "values": [
                            (0 if g.get("monto") is None else float(g.get("monto"))) for g in gastos_por_categoria_out
                        ],
                    },
                }
                summaries.append(summary)

            if is_admin_like:
                turnos_block_list = summaries
            else:
                # Vendedor: si tiene, exponer también en la clave anterior para compatibilidad
                turno_block = summaries[0] if summaries else {"activo": False}

        # Bloque de usuario
        user_block = {
            "id": user.id,
            "username": user.username,
            "nombre": f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip(),
            "groups": list(groups),
            "role_resuelto": role,
        }

        payload = {
            "last_updated": timezone.now(),
            "filters": {
                "business_uid": str(getattr(business, 'uid', '')),
                "period": period,
                "date_from": date_from,
                "date_to": date_to,
                "role": role_param or role,
                "group_by": group_by,
                "top_n": top_n,
            },
            "user": user_block,
            "inventory": inventory_block,
            "ventas_hoy": ventas_block,
            "proveedor_recepciones": recepciones_block,
            "proveedor_pagos": pagos_block,
            "turno": turno_block,
            "turnos": turnos_block_list,
            # Sugerencia de layout para el frontend: mostrar ventas y turno en columnas con gráfico a un lado
            "layout_hints": {
                "rows": [
                    {"type": "columns", "blocks": ["ventas_hoy", "turno"]}
                ]
            },
        }

        # Analítica ampliada (series y breakdowns)
        # Determinar inclusiones
        default_includes = {
            "ventas_timeseries",
            "pagos_timeseries",
            "recepciones_timeseries",
            "ventas_por_producto_top",
            "pagos_por_metodo_ts",
        }
        if include_param:
            requested_includes = {p.strip() for p in include_param.split(',') if p.strip()}
        else:
            requested_includes = default_includes

        # Helper para truncar por periodo
        if group_by == 'week':
            trunc = TruncWeek
        elif group_by == 'month':
            trunc = TruncMonth
        else:
            trunc = TruncDate

        # ventas_timeseries
        if 'ventas_timeseries' in requested_includes:
            if role == 'Proveedor' and proveedor:
                items_qs = SaleItem.objects.filter(
                    venta__business=business,
                    venta__cancelada=False,
                    venta__created_at__range=(start_dt, end_dt),
                ).filter(
                    Q(lote__proveedor=proveedor) | Q(proveedor_original=proveedor) | Q(lote__propietario_original=proveedor)
                )
                qs = items_qs.annotate(bucket=trunc('venta__created_at')).values('bucket').annotate(
                    ventas=Count('venta_id', distinct=True),
                    cajas=Coalesce(Sum('unidades_vendidas'), 0),
                    monto=Coalesce(Sum('subtotal'), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2)),
                ).order_by('bucket')
            else:
                ventas_qs = Sale.objects.filter(business=business, cancelada=False, created_at__range=(start_dt, end_dt))
                qs = ventas_qs.annotate(bucket=trunc('created_at')).values('bucket').annotate(
                    ventas=Count('id'),
                    cajas=Coalesce(Sum('cajas_vendidas'), 0),
                    monto=Coalesce(Sum('total'), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2)),
                ).order_by('bucket')

            serie = []
            for row in qs:
                serie.append({
                    "date": row['bucket'],
                    "ventas": int(row['ventas'] or 0),
                    "cajas": int(row['cajas'] or 0),
                    "monto": None if (not is_admin_like and role != 'Proveedor') else float(row['monto'] or 0),
                })
            payload["ventas_timeseries"] = serie

        # pagos_timeseries
        if 'pagos_timeseries' in requested_includes:
            pagos_qs = SupplierPayment.objects.filter(
                business=business,
                fecha_pago__range=(start_dt, end_dt),
            )
            if role == 'Proveedor' and proveedor:
                pagos_qs = pagos_qs.filter(recepcion__proveedor=proveedor)
            qs = pagos_qs.annotate(bucket=trunc('fecha_pago')).values('bucket').annotate(
                pagos=Count('id'),
                monto=Coalesce(Sum('monto'), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2)),
            ).order_by('bucket')
            serie = []
            for row in qs:
                serie.append({
                    "date": row['bucket'],
                    "pagos": int(row['pagos'] or 0),
                    "monto": None if (not is_admin_like and role != 'Proveedor') else float(row['monto'] or 0),
                })
            payload["pagos_timeseries"] = serie

        # recepciones_timeseries
        if 'recepciones_timeseries' in requested_includes:
            rec_qs = GoodsReception.objects.filter(
                business=business,
                fecha_recepcion__range=(start_dt, end_dt),
            )
            if role == 'Proveedor' and proveedor:
                rec_qs = rec_qs.filter(proveedor=proveedor)
            qs = rec_qs.annotate(bucket=trunc('fecha_recepcion')).values('bucket').annotate(
                recepciones=Count('id'),
                cajas=Coalesce(Sum('total_cajas'), 0),
                peso_bruto=Coalesce(Sum('total_peso_bruto'), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2)),
                monto=Coalesce(Sum('monto_total'), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2)),
                pagadas=Sum(Case(When(estado_pago='pagado', then=1), default=0, output_field=IntegerField())),
                pendientes=Sum(Case(When(estado_pago='pendiente', then=1), default=0, output_field=IntegerField())),
            ).order_by('bucket')
            serie = []
            for row in qs:
                serie.append({
                    "date": row['bucket'],
                    "recepciones": int(row['recepciones'] or 0),
                    "cajas": int(row['cajas'] or 0),
                    "peso_bruto": None if (not is_admin_like and role != 'Proveedor') else float(row['peso_bruto'] or 0),
                    "monto": None if (not is_admin_like and role != 'Proveedor') else float(row['monto'] or 0),
                    "pagadas": int(row['pagadas'] or 0),
                    "pendientes": int(row['pendientes'] or 0),
                })
            payload["recepciones_timeseries"] = serie

        # ventas_por_producto_top (ranking por subtotal y cantidad)
        if 'ventas_por_producto_top' in requested_includes:
            if role == 'Proveedor' and proveedor:
                items_qs = SaleItem.objects.filter(
                    venta__business=business,
                    venta__cancelada=False,
                    venta__created_at__range=(start_dt, end_dt),
                ).filter(
                    Q(lote__proveedor=proveedor) | Q(proveedor_original=proveedor) | Q(lote__propietario_original=proveedor)
                )
            else:
                items_qs = SaleItem.objects.filter(
                    venta__business=business,
                    venta__cancelada=False,
                    venta__created_at__range=(start_dt, end_dt),
                )

            # Agrupar por nombre de producto correcto: si viene de BIN usar bin__producto__nombre, si no lote__producto__nombre
            items_qs = items_qs.annotate(
                producto_nombre=Case(
                    When(bin__isnull=False, then=F('bin__producto__nombre')),
                    When(lote__isnull=False, then=F('lote__producto__nombre')),
                    default=Value(''),
                    output_field=CharField(max_length=128),
                )
            )

            agg = items_qs.values('producto_nombre').annotate(
                ventas=Count('venta_id', distinct=True),
                cajas=Coalesce(Sum('unidades_vendidas'), 0),
                monto=Coalesce(Sum('subtotal'), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2)),
            ).order_by('-monto', '-cajas')[:top_n]

            ranking = []
            for row in agg:
                ranking.append({
                    "producto": row['producto_nombre'] or '',
                    "ventas": int(row['ventas'] or 0),
                    "cajas": int(row['cajas'] or 0),
                    "monto": None if (not is_admin_like and role != 'Proveedor') else float(row['monto'] or 0),
                })
            payload['ventas_por_producto_top'] = ranking

        # pagos_por_metodo_ts (serie)
        if 'pagos_por_metodo_ts' in requested_includes:
            pagos_qs = SupplierPayment.objects.filter(
                business=business,
                fecha_pago__range=(start_dt, end_dt),
            )
            if role == 'Proveedor' and proveedor:
                pagos_qs = pagos_qs.filter(recepcion__proveedor=proveedor)
            qs = pagos_qs.annotate(bucket=trunc('fecha_pago')).values('bucket', 'metodo_pago').annotate(
                pagos=Count('id'),
                monto=Coalesce(Sum('monto'), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2)),
            ).order_by('bucket', 'metodo_pago')

            serie = []
            for row in qs:
                serie.append({
                    "date": row['bucket'],
                    "metodo": row['metodo_pago'],
                    "pagos": int(row['pagos'] or 0),
                    "monto": None if (not is_admin_like and role != 'Proveedor') else float(row['monto'] or 0),
                })
            payload['pagos_por_metodo_ts'] = serie

        return Response(payload)
