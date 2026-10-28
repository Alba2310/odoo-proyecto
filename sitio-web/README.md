# Sitio web de venta de AutoFlow

Sitio estático (HTML, CSS y JavaScript, sin dependencias) para vender el módulo `autoflow_management`.
Se adapta a computadora, tablet y celular.

## Páginas

| Archivo | Contenido |
|---|---|
| `index.html` | Portada: problema/solución, funciones, recorrido de una orden, capturas, calculadora de ahorro |
| `funciones.html` | Detalle de cada parte del sistema con capturas reales y permisos |
| `demo.html` | Demo interactiva del taller: recepción, tablero, checklist, firma, aviso y factura (simulados en el navegador) |
| `precios.html` | Planes mensual/anual, comparación y preguntas frecuentes |
| `contacto.html` | Formulario de solicitud de demo |
| `llamar/index.html` | Tarjeta con el teléfono: llamar, WhatsApp y copiar el número. Se abre con `tusitio/llamar` |

En el celular, el teléfono del sitio abre el marcador; en la computadora lleva a `llamar/`, porque los links
`tel:` no hacen nada si no hay una app de llamadas instalada.

## Cómo verlo

Con Docker Desktop abierto, el servicio `sitio` de `docker-compose.yml` (nginx) lo sirve en http://localhost:5500.
Arranca solo junto con Docker; si no, prendelo con:

```bash
docker compose up -d sitio
```

También se puede abrir `index.html` con doble clic, sin servidor.

## Qué cambiar antes de publicarlo

1. **Datos de contacto** (WhatsApp, teléfono, correo, dirección): están en `CONFIG`, al principio de `js/main.js`.
   Se actualizan solos en todo el sitio (y en el número de respaldo de `llamar/index.html`).
2. **Precios**: son valores de referencia. Cada plan tiene el precio mensual en `data-precio-mensual`
   y en el texto de `.plan__monto` (`precios.html`). El precio anual se calcula solo (12 meses por el precio de 10).
   Los extras y la tabla comparativa también están en `precios.html`.
3. **Horario de atención**: en `contacto.html`.

## Formulario de contacto

Al enviarlo, el sitio manda la solicitud al Odoo de `CONFIG.odoo` (`js/main.js`), donde el módulo
`extra-addons/autoflow_sitio_web` la guarda como oportunidad del CRM y envía un correo de aviso.
Después el cliente puede escribirte también por WhatsApp con el mensaje ya armado.

Si Odoo no responde (apagado o sin acceso desde internet), no se pierde nada: el sitio le pide al cliente
que la envíe por WhatsApp o por correo con un toque.

- Hoy `CONFIG.odoo` está vacío: el CRM (base `autoflow_ventas`, servicio `ventas`) se quitó el 28/10/2026 y
  el cliente siempre la envía por WhatsApp o correo. Para volver a usarlo: restaurar el respaldo de esa base,
  volver a agregar el servicio `ventas` a `docker-compose.yml` (está en el historial de git) y poner
  `http://localhost:8070` en `CONFIG.odoo`.
- Para que salgan los correos, cargá la contraseña de aplicación de Gmail en el servidor "Gmail"
  (Ajustes → Técnico → Servidores de correo saliente).
- Al publicar el sitio, `CONFIG.odoo` tiene que ser una dirección **https** de ese Odoo accesible desde internet;
  `localhost` solo funciona en tu computadora.

## Capturas

`img/capturas/` tiene las pantallas de `presentacion/imagenes/` convertidas a JPG de 1600 px de ancho
para que el sitio cargue rápido en el celular.
