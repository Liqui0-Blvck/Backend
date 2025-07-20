# Ejemplos de uso de HTTPie para probar la API FruitPOS

> Asegúrate de tener HTTPie instalado: https://httpie.io/docs/cli/installation

## Autenticación (obtener token JWT)

```bash
http POST http://localhost:8000/api/v1/token/ username=="admin" password=="tu_password"
```

La respuesta incluirá `access` y `refresh` tokens.

---

## Enviar mensaje simulado a webhook de WhatsApp (Twilio)

```bash
http POST http://localhost:8000/api/v1/whatsapp/webhook/twilio/ \
  From=="whatsapp:+56912345678" \
  Body=="Hola, quiero comprar 10kg de manzanas"
```

---

## Listar mensajes pendientes (requiere token)

```bash
http GET http://localhost:8000/api/v1/whatsapp/salepending/ \
  'Authorization: Bearer <ACCESS_TOKEN>'
```

---

## Responder a un mensaje pendiente (requiere token, ENVÍA WhatsApp real)

```bash
http POST http://localhost:8000/api/v1/whatsapp/salepending/1/responder/ \
  respuesta="¡Hola! Gracias por tu interés. Tenemos manzanas frescas disponibles." \
  'Authorization: Bearer <ACCESS_TOKEN>'
```

- Si tu entorno y credenciales Twilio están configurados, este comando enviará la respuesta al WhatsApp real del cliente.
- Si ocurre un error, verás el detalle en la respuesta.

---

## Listar clientes de WhatsApp (requiere token)

```bash
http GET http://localhost:8000/api/v1/whatsapp/customers/ \
  'Authorization: Bearer <ACCESS_TOKEN>'
```

---

## Crear cliente de WhatsApp manualmente (requiere token)

```bash
http POST http://localhost:8000/api/v1/whatsapp/customers/ \
  nombre="Juan Perez" \
  whatsapp="whatsapp:+56912345678" \
  business=1 \
  'Authorization: Bearer <ACCESS_TOKEN>'
```

---

## Notas
- Cambia `localhost:8000` por tu host si es necesario.
- Usa el token JWT obtenido en autenticación para las rutas protegidas.
- Puedes agregar más ejemplos según tus endpoints personalizados.
