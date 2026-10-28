# Sitio web de venta de Óga

Página única para vender Óga (módulo `extra-addons/alquileres`). Es distinta de los sitios de AutoFlow y Studio
Bella a propósito: una sola página que se lee de corrido, en crema, verde bosque y terracota, con el ñandutí como
motivo. Se ve en http://localhost:5502 (servicio `sitio-oga` de `docker-compose.yml`).

## Qué tiene

1. Portada con un celular que muestra la charla de WhatsApp: el aviso, la respuesta y la confirmación del pago.
2. “¿Te suena?”: los problemas de siempre al cobrar alquileres.
3. “Un mes con Óga”: los cinco pasos de cada mes.
4. Tablero de prueba (`js/main.js`, `UNIDADES`): las mismas 7 unidades del sistema de ejemplo. Se puede tocar cada
   una, ver el mensaje de WhatsApp y registrar un pago (la unidad pasa a verde).
5. Funciones en mosaico.
6. Calculadora de horas y plata que se cobra antes (cuenta aproximada, explicada en la página).
7. Precios según la cantidad de unidades.
8. “Hecho acá”, preguntas frecuentes y formulario.

## Para cambiar

- **Contacto y precios**: `CONFIG` al principio de `js/main.js`. Los precios son valores de referencia.
- El formulario no guarda nada: arma el mensaje con los datos y abre WhatsApp al número de `CONFIG.whatsapp`.
- El ícono (`img/icon.png`) es el mismo del módulo.
