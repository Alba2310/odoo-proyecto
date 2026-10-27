# Sitio web de venta de Studio Bella

Sitio estático (HTML, CSS y JavaScript, sin dependencias) para vender el módulo `studio_bella`, el sistema para
peluquerías. Se adapta a computadora, tablet y celular. Parte de la misma base que el sitio de AutoFlow
(`sitio-web/`), pero tiene un estilo propio para que no se parezcan: fondos claros en crema y rosa, arcos, letra
DM Sans con títulos en Fraunces y la paleta ciruela y rosa. Ese estilo está en la «Capa Studio Bella», al final de
`css/estilos.css`, que pisa las reglas de la base.

## Páginas

| Archivo | Contenido |
|---|---|
| `index.html` | Portada: celular con el recordatorio, problema/solución, funciones en mosaico, carta de servicios con precios de ejemplo, un turno paso a paso, capturas, recordatorio por WhatsApp, calculadora de turnos perdidos |
| `funciones.html` | Detalle de cada parte del sistema con capturas reales, permisos y manual |
| `demo.html` | Demo interactiva: agendar (con las validaciones del sistema), recordar por WhatsApp, cobrar con factura y reponer stock. Todo simulado en el navegador (`js/demo.js`) |
| `precios.html` | Planes mensual/anual, comparación y preguntas frecuentes |
| `contacto.html` | Formulario para pedir una demostración |
| `llamar/index.html` | Tarjeta con el teléfono: llamar, WhatsApp y copiar el número. Se abre con `tusitio/llamar` |

Las capturas de `img/capturas/` son las del manual de usuario del módulo (`extra-addons/studio_bella/static/manual/img/`).

## Cómo verlo

Con Docker levantado, el servicio `sitio-bella` de `docker-compose.yml` (nginx) lo sirve en http://localhost:5501:

```bash
docker compose up -d sitio-bella
```

También se puede abrir `index.html` con doble clic, sin servidor.

## Qué cambiar antes de publicarlo

1. **Datos de contacto** (WhatsApp, teléfono, correo, dirección): están en `CONFIG`, al principio de `js/main.js`.
   Hoy son los mismos que los del sitio de AutoFlow.
2. **Precios**: son valores de referencia. Cada plan tiene el precio mensual en `data-precio-mensual` y en el texto
   de `.plan__monto` (`precios.html`). El precio anual se calcula solo (12 meses por el precio de 10).
   Los extras y la tabla comparativa también están en `precios.html`.
3. **Horario de atención**: en `contacto.html` y `llamar/index.html`.

## Formulario de contacto

Usa el mismo CRM que AutoFlow: el formulario manda la solicitud a `CONFIG.odoo` (servicio `ventas`, base
`autoflow_ventas`, http://localhost:8070) con `producto=studio_bella`. El módulo `extra-addons/autoflow_sitio_web`
la guarda como oportunidad "Demo Studio Bella · …" con las etiquetas "Sitio web" y "Studio Bella" y manda el aviso
por correo. Si Odoo no responde, el sitio le ofrece al cliente enviarla por WhatsApp o por correo con un toque.

Al publicar el sitio, `CONFIG.odoo` tiene que ser una dirección **https** de ese Odoo accesible desde internet;
`localhost` solo funciona en tu computadora.
