# Proyecto Odoo 18 (Docker)

Módulos propios de Odoo 18 Community en `extra-addons/`, levantados con `docker compose` (ver README.md).

- `studio_bella`: sistema de la peluquería Studio Bella (citas, cobro con factura, productos con stock, compras,
  recordatorios por correo y WhatsApp, turnos por internet, cierre de caja, clientas que no vuelven, ficha técnica,
  comisiones, programa de puntos, manual de usuario).
  Detalle en `extra-addons/studio_bella/README.md`. Su página pública de turnos la atiende el servicio `turnos`
  (puerto 8071, solo la base `peluqueria`): http://127.0.0.1:8071/turnos.
- `autoflow_management`: concesionaria y taller, en la base `autoflow_py` (admin / admin); su sitio de venta
  es `sitio-web/` (puerto 5500).
- `sitio-bella/`: sitio de venta de Studio Bella (puerto 5501), hecho sobre la base de `sitio-web/`.
- `sitio-oga/`: sitio de venta de Óga (puerto 5502): una sola página con diseño propio, a pedido del usuario
  distinto de los otros dos. El formulario arma el mensaje y abre WhatsApp (no hay CRM).
- `autoflow_sitio_web`: guardaba en un CRM los formularios de los dos sitios (campo `producto`). Su base
  `autoflow_ventas` y el servicio `ventas` (8070) se quitaron el 2026-10-28; los sitios tienen `CONFIG.odoo` vacío.
- `alquileres` (producto **Óga**): control de alquileres (contratos, cobros con aviso por WhatsApp, gastos y
  ganancia, mantenimiento, actas, depósito, página pública "Se alquila"), base `alquileres` (admin / admin).
  La página la atiende el servicio `oga` (puerto 8072, solo esa base): http://se-alquila.localhost:8072/se-alquila.
  Se crea con
  `bash extra-addons/alquileres/scripts/crear_alquileres.sh`. Detalle en `extra-addons/alquileres/README.md`.
- `veterinaria` (producto **Patitas**): veterinaria (mascotas con línea de tiempo y peso, historia clínica, carnet
  de vacunas con aviso de la próxima dosis, baño y peluquería, internación y hotel, cobro mixto con factura, stock y
  compras, tablero "Hoy en Patitas", turnos por internet tipo chat). A pedido del usuario, con identidad y pantallas
  propias, distintas de Studio Bella. Base `veterinaria` (admin / admin), se crea con
  `bash extra-addons/veterinaria/scripts/crear_veterinaria.sh`. La página `/reservar` la atiende el servicio
  `patitas` (puerto 8073, solo esa base): http://patitas.localhost:8073/reservar. Detalle en
  `extra-addons/veterinaria/README.md`.
- `sitio-patitas/`: sitio de venta de Patitas (puerto 5503). A pedido del usuario, que no se parezca en nada a los
  otros tres y que sea divertido: mascota interactiva, "un día" que corre al bajar, un juego de la sala de espera,
  álbum de figuritas. El formulario abre WhatsApp, como el de Óga.
- `tienda_*` y `mi_modulo`: módulos de práctica.

## Cómo trabajar

- Responder en español (Paraguay). Los módulos propios usan nombres técnicos y textos en español
  (salvo `autoflow_management`, que tiene nombres técnicos en inglés).
- Moneda guaraníes (PYG, sin decimales) e IVA 10 % / 5 % incluido en el precio.
- La base de la peluquería es `peluqueria` (admin / admin); se crea con
  `bash extra-addons/studio_bella/scripts/crear_peluqueria.sh`.
- Tests: `bash scripts/pruebas.sh studio_bella` (o `alquileres`, `veterinaria`, `autoflow_management`). Corren en una base aparte,
  `pruebas_<módulo>`, que el script crea la primera vez; nunca en las bases que usa el usuario.
  Por dentro usa `--http-port=8079` porque el contenedor `web` ya usa el 8069, así que de a un módulo por vez.
- Cambios en Python: reiniciar con `docker compose restart web turnos oga patitas`. Cambios solo en XML o JS: alcanza con
  `-u studio_bella` (los archivos de `static/turnos/` ni eso: se leen del disco).
- No borrar ni regenerar datos de una base que se esté usando: actualizar con `-u`.

## Cosas que no son obvias

- El plan contable genérico deja la moneda en USD al instalar Facturación: `configurar_base.py` la cambia a PYG.
- En Odoo 18 los precios de producto usan `min_display_digits`: para verlos sin decimales, `widget="monetary"`.
- Odoo guarda los archivos estáticos una semana en caché del navegador (por eso el manual se abre con `?v=`).
- En `<function>` de XML no se puede usar `eval` junto con hijos `<value>`.
- Validar entregas desde scripts necesita `with_context(skip_sms=True)`.
- Una ruta pública (`auth='public'`) solo funciona si Odoo sabe la base: sesión ya iniciada, una sola base o
  `--db-filter`. Por eso los servicios `turnos` (8071) y `oga` (8072) son Odoo aparte con `--db-filter`.
- Con la caja de un día cerrada no se puede cobrar con esa fecha: no cerrar la caja de hoy en la base en uso.
- Las secuencias de PostgreSQL (pedidos de compra, etc.) no se deshacen con los tests: por eso los tests van en
  las bases `pruebas_*` y no en las reales.
- El recordatorio por WhatsApp abre `wa.me` con el mensaje escrito (sin la API paga de WhatsApp Business), por decisión del usuario.
