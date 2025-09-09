# API Proveedores (Suppliers)

Documenta endpoints, payloads esperados y respuestas del módulo de Proveedores.

Base URL: `https://TU_DOMINIO/api/v1/inventory/`
Autenticación: `Authorization: Bearer <token>`

---

## 1. Proveedores

### 1.1 Listar proveedores
GET `/suppliers/`

Respuesta (200): arreglo de proveedores (serializador `SupplierSerializerList`).

### 1.2 Detalle de proveedor
GET `/suppliers/{supplier_uid}/`

Incluye:
- Métricas: `total_deuda`, `total_pagado`
- Listas filtradas (excluye recepciones con `estado='rechazado'`):
  - `recepciones_pendientes` (últimas 5)
  - `detalle_pallets` (pallets de recepciones)
  - `detalle_bins` (bins del proveedor)
  - `detalle_pallets_desde_bins` (pallets originados por transformación desde bins del proveedor)
- Últimos eventos: `ultima_recepcion`, `ultimo_pago`
- Resúmenes: `resumen_pagos`, `resumen_liquidaciones`

Ejemplo (fragmento):
```json
{
  "uid": "<SUPPLIER_UID>",
  "nombre": "Matriz Fruticola",
  "total_deuda": 23568800.0,
  "recepciones_pendientes": [
    {"uid": "...", "numero_guia": "GE-2025-0006", "estado_pago": "pendiente"}
  ],
  "detalle_pallets": [
    {"uid": "<DETALLE_UID>", "numero_pallet": "P1", "producto": "Palta", "numero_guia": "GE-2025-0006"}
  ],
  "detalle_bins": [
    {"uid": "<BIN_UID>", "codigo": "BIN-ABCD1234", "producto_nombre": "Palta", "estado_display": "Disponible"}
  ],
  "detalle_pallets_desde_bins": [
    {"lote_uid": "<LOTE_UID>", "producto": "Palta", "origen": "bin"}
  ]
}
```

### 1.3 Transacciones del proveedor (todas sus recepciones)
GET `/suppliers/{supplier_uid}/transactions/`

---

## 2. Recepciones (GoodsReception)

### 2.1 Listar recepciones
GET `/goodsreceptions/`


### 2.3 Detalle de recepción
GET `/goodsreceptions/{uid}/`

Incluye `detalles` con campos: `numero_pallet`, `producto`, `cantidad_cajas`, `peso_bruto`, `peso_tara`, `costo`, `en_concesion`, `comision_por_kilo`, `fecha_limite_concesion`, y (para UI) `comision_base`, `comision_monto`, `comision_porcentaje`.

### 2.4 Actualizar recepción
PATCH `/goodsreceptions/{uid}/`
---
## 3. Pagos a Proveedor (SupplierPayment)

### 3.1 Listar pagos
GET `/supplier-payments/`

### 3.2 Crear pago
POST `/supplier-payments/`

Campos (serializador `SupplierPaymentSerializer`):
- `recepcion`: ID (int) de la recepción
- `monto`: decimal
- `fecha_pago`: ISO (opcional; por defecto now)
- `metodo_pago`: 'efectivo' | 'transferencia' | 'cheque' | 'otro'
- `comprobante`: archivo (opcional, multipart)
- `notas`: string (opcional)

Ejemplo:
```json
{
  "recepcion": 123,
  "monto": 250000.00,
  "metodo_pago": "transferencia",
  "notas": "Abono parcial"
}
```

---

## 4. Liquidaciones de Concesión

### 4.1 Listar
GET `/concession-settlements/`

### 4.2 Crear liquidación
POST `/concession-settlements/`

Ejemplo:
```json
{
  "proveedor": 45,
  "fecha_liquidacion": "2025-09-08",
  "total_kilos_vendidos": 1234.50,
  "total_ventas": 2500000.00,
  "total_comision": 123000.00,
  "monto_a_liquidar": 2377000.00,
  "estado": "pendiente",
  "notas": "Liquidación período semanal"
}
```

### 4.3 Marcar como pagada
POST `/concession-settlements/{uid}/marcar_como_pagado/`

### 4.4 Cancelar
POST `/concession-settlements/{uid}/cancelar/`

---

## 5. Bins y Pallets (para proveedor)

### 5.1 Bins del proveedor
En el detalle del proveedor: `detalle_bins` (excluye bins cuya recepción esté `rechazado`).

### 5.2 Pallets desde bins del proveedor
En el detalle del proveedor: `detalle_pallets_desde_bins` (usa trazabilidad de `BinToLotTransformationDetail`).

---

## Notas operativas
- Para persistir comisión sin migraciones, usa base `kg` y detalla el `costo` de los pallets de palta.
- Recepciones rechazadas se excluyen de listados del detalle del proveedor.
- Los endpoints aceptan UIDs para entidades clave, excepto `SupplierPayment.recepcion` que usa ID (FK int).

---

## 6. Anexo: Ejemplos JSON para el Frontend

Los siguientes ejemplos muestran exactamente lo que espera el backend (entrada) y lo que retorna (salida) en los serializadores de detalle. No hay cálculos automáticos; los campos de concesión se guardan tal como se envían.

### 6.1 POST /goodsreceptions/ (crear recepción)
```json
{
  "proveedor": "fa0c4477-b6cf-4b11-8a84-fb48817a67e7",
  "recibido_por": 2,
  "estado": "pendiente",
  "observaciones": "",
  "estado_pago": "pendiente",
  "en_concesion": true,
  "comision_base": "kg",
  "comision_monto": 175.0,
  "comision_porcentaje": null,
  "comision_por_kilo": 175.0,
  "fecha_limite_concesion": "2025-09-30",
  "detalles": [
    {
      "producto": "441836fa-baa8-48ab-9581-6da34554f124",
      "box_type": "f1342038-f900-4f90-a664-89d3025c608e",
      "numero_pallet": "P1",
      "variedad": "Hass",
      "calibre": "22",
      "cantidad_cajas": 104,
      "peso_bruto": 1075.0,
      "peso_tara": 35.0,
      "costo": 1950.0,
      "calidad": 4,
      "estado_maduracion": "verde",
      "porcentaje_perdida_estimado": 3.0,
      "en_concesion": true,
      "comision_por_kilo": 175.0,
      "fecha_limite_concesion": "2025-09-30"
    }
  ]
}
```

### 6.2 GET /goodsreceptions/{uid}/ (detalle de recepción)
```json
{
  "uid": "7e37a720-3c3a-42ef-8e10-e81448d48297",
  "numero_guia": "GE-2025-0008",
  "fecha_recepcion": "2025-09-08T22:30:54.927930-03:00",
  "proveedor": 1,
  "proveedor_info": {
    "uid": "fa0c4477-b6cf-4b11-8a84-fb48817a67e7",
    "nombre": "Matriz Fruticola",
    "rut": "77.388.071-9",
    "telefono": "+569 36238503",
    "email": "admin@matrizfruticola.cl"
  },
  "estado": "pendiente",
  "estado_pago": "pendiente",
  "en_concesion": true,
  "comision_base": "kg",
  "comision_monto": 175.0,
  "comision_porcentaje": null,
  "comision_por_kilo": 175.0,
  "fecha_limite_concesion": "2025-09-30",
  "total_pallets": 1,
  "total_cajas": 104,
  "total_peso_bruto": "1075.00",
  "detalles": [
    {
      "uid": "4b74048f-e0fb-4a1d-85f9-6664743894c0",
      "numero_pallet": "P1",
      "producto": "441836fa-baa8-48ab-9581-6da34554f124",
      "producto_nombre": "Palta",
      "box_type": "f1342038-f900-4f90-a664-89d3025c608e",
      "box_type_nombre": "Toro",
      "variedad": "Hass",
      "calibre": "22",
      "calidad": 4,
      "estado_maduracion": "verde",
      "cantidad_cajas": 104,
      "peso_bruto": 1075.0,
      "peso_tara": 35.0,
      "costo": 1950.0,
      "porcentaje_perdida_estimado": 3.0,
      "precio_sugerido_min": null,
      "precio_sugerido_max": null,
      "en_concesion": true,
      "comision_por_kilo": 175.0,
      "fecha_limite_concesion": "2025-09-30",
      "comision_base": "kg",
      "comision_monto": 175.0,
      "comision_porcentaje": null,
      "lote_id": null
    }
  ]
}
```

### 6.3 PATCH /goodsreceptions/{uid}/ (actualizar recepción)
```json
{
  "en_concesion": true,
  "comision_base": "caja",
  "comision_monto": 500.0,
  "comision_porcentaje": null,
  "comision_por_kilo": null,
  "fecha_limite_concesion": "2025-10-15"
}
```

### 6.4 POST /receptiondetails/bulk_create/ (crear/actualizar detalles)
```json
{
  "recepcion_uid": "7e37a720-3c3a-42ef-8e10-e81448d48297",
  "detalles": [
    {
      "producto": "441836fa-baa8-48ab-9581-6da34554f124",
      "numero_pallet": "P2",
      "cantidad_cajas": 100,
      "peso_bruto": 1000.0,
      "peso_tara": 35.0,
      "costo": 1900.0,
      "en_concesion": true,
      "comision_por_kilo": 160.0,
      "fecha_limite_concesion": "2025-09-30"
    },
    {
      "uid": "4b74048f-e0fb-4a1d-85f9-6664743894c0",
      "numero_pallet": "P1",
      "cantidad_cajas": 108,
      "comision_por_kilo": 175.0
    }
  ]
}
```

### 6.5 GET /fruits/{uid}/ (detalle de Lote)
```json
{
  "uid": "b8d54f8c-6c6d-4f52-8f73-9e9a0d77c111",
  "producto": "441836fa-baa8-48ab-9581-6da34554f124",
  "variedad": "Hass",
  "proveedor": 1,
  "procedencia": "Lo valledor",
  "en_concesion": true,
  "comision_por_kilo": 175.0,
  "fecha_limite_concesion": "2025-09-30",
  "propietario_original": 1,
  "cantidad_cajas": 104,
  "peso_bruto": 1075.0,
  "peso_neto": 1040.0,
  "precio_sugerido_min": null,
  "precio_sugerido_max": null,
  "estado_maduracion": "verde",
  "fecha_ingreso": "2025-09-08"
}
```

### 6.6 POST /fruitbins/ (crear Bin)
```json
{
  "codigo": "BIN-0001",
  "producto": "441836fa-baa8-48ab-9581-6da34554f124",
  "variedad": "Hass",
  "business": 1,
  "peso_bruto": 520.0,
  "peso_tara": 20.0,
  "costo_por_kilo": 1750.0,
  "costo_total": null,
  "proveedor": "fa0c4477-b6cf-4b11-8a84-fb48817a67e7",
  "recepcion": "7e37a720-3c3a-42ef-8e10-e81448d48297",
  "en_concesion": true,
  "comision_por_kilo": 180.0,
  "fecha_limite_concesion": "2025-09-30",
  "temperatura": null,
  "observaciones": ""
}
```

### 6.7 GET /fruitbins/{uid}/ (detalle de Bin)
```json
{
  "uid": "bd4b3e4c-6b2f-4f2a-8c9e-2b5b3d1c7a22",
  "codigo": "BIN-0001",
  "producto": "441836fa-baa8-48ab-9581-6da34554f124",
  "producto_nombre": "Palta",
  "producto_tipo": "palta",
  "proveedor": "fa0c4477-b6cf-4b11-8a84-fb48817a67e7",
  "proveedor_nombre": "Matriz Fruticola",
  "recepcion": "7e37a720-3c3a-42ef-8e10-e81448d48297",
  "variedad": "Hass",
  "peso_bruto": 520.0,
  "peso_tara": 20.0,
  "peso_neto": 500.0,
  "costo_por_kilo": 1750.0,
  "costo_total": null,
  "en_concesion": true,
  "comision_por_kilo": 180.0,
  "fecha_limite_concesion": "2025-09-30",
  "estado": "DISPONIBLE",
  "calidad": 4,
  "ubicacion": "BODEGA",
  "fecha_recepcion": "2025-09-08",
  "temperatura": null,
  "observaciones": ""
}
```





