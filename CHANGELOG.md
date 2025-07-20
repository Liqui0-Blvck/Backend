# 📦 FruitPOS - CHANGELOG

Registro detallado de cambios por aplicación y fecha. Actualiza aquí cada vez que realices un cambio relevante.

---

## 2025-06

### 📦 [inventory] Sistema de Recepción de Mercadería
- Implementado nuevo sistema para gestionar la recepción de fruta en bodega (guías de entrada).
- Creados modelos `Proveedor`, `RecepcionMercaderia`, `DetalleRecepcion` e `ImagenRecepcion`.
- Integración con el sistema de inventario existente mediante trazabilidad hacia lotes (`FruitLot`).
- Soporte para registro detallado de pallets con información de calidad, peso, temperatura y estado.
- Cálculo automático de totales (pallets, cajas, peso) en cada recepción.
- Flujo de estados para seguimiento del proceso (pendiente, revisado, aprobado, rechazado).

### 🔒 [accounts] Seguridad y Autenticación JWT
- Implementado login, refresh y logout usando JWT en cookies httpOnly, Secure, SameSite=Strict.
- Los tokens nunca se exponen en el body, solo en cookies.
- Nuevo endpoint `/accounts/logout/` para cerrar sesión eliminando ambas cookies.
- Clase global `CustomJWTAuthentication` busca JWT en header Authorization o en cookie.
- El frontend solo debe usar `withCredentials: true`.
- Beneficio: máxima protección contra XSS y manejo seguro de sesiones.

### 🗃️ [sales] Gestión de pre-reservas
- El modelo y API de pre-reservas (`SalePending`) se gestionan 100% desde la app `sales`.
- Eliminadas todas las referencias a pre-reservas en la app `whatsapp`.
- Endpoints REST claros para ventas y pre-reservas.

### ⚡ [core] Otros cambios generales
- Documentación y comentarios mejorados.
- Configuración CORS robusta para desarrollo y producción.
- Preparado para integración frontend Next.js y despliegue en DigitalOcean.

---

## ¿Cómo actualizar este changelog?
- Agrega una sección por mes o sprint.
- Detalla los cambios por app: `[accounts]`, `[sales]`, `[inventory]`, `[core]`, etc.
- Sé claro y específico para facilitar el trabajo a otros desarrolladores.
