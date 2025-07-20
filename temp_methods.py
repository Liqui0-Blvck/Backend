def get_peso_vendido(self, obj):
    # Importar Sale aquí para evitar importaciones circulares
    from sales.models import Sale
    # Sumar el peso vendido de todas las ventas asociadas a este lote
    ventas = Sale.objects.filter(lote=obj)
    total_vendido = sum(float(venta.peso_vendido or 0) for venta in ventas)
    return round(total_vendido, 2)

def get_dinero_generado(self, obj):
    # Importar Sale aquí para evitar importaciones circulares
    from sales.models import Sale
    # Sumar el total de todas las ventas asociadas a este lote
    ventas = Sale.objects.filter(lote=obj)
    total_generado = sum(float(venta.total or 0) for venta in ventas)
    return round(total_generado, 2)

def get_porcentaje_vendido(self, obj):
    # Calcular el porcentaje del peso total que ha sido vendido
    peso_total = float(obj.peso_neto or 0)
    if peso_total <= 0:
        return 0
    
    peso_vendido = self.get_peso_vendido(obj)
    porcentaje = (peso_vendido / peso_total) * 100
    return round(porcentaje, 2)
