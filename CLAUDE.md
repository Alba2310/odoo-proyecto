# Proyecto Odoo 18 (Docker)

Módulos propios de Odoo 18 Community en `extra-addons/`, levantados con `docker compose` (ver README.md).

- `studio_bella`: sistema de la peluquería Studio Bella (citas, cobro con factura, productos con stock, compras,
  recordatorios por correo y WhatsApp, manual de usuario). Detalle en `extra-addons/studio_bella/README.md`.
- `autoflow_management` y `autoflow_sitio_web`: concesionaria y taller, y el CRM de su sitio web (`sitio-web/`).
- `tienda_*` y `mi_modulo`: módulos de práctica.

## Cómo trabajar

- Responder en español (Paraguay). Los módulos propios usan nombres técnicos y textos en español
  (salvo `autoflow_management`, que tiene nombres técnicos en inglés).
- Moneda guaraníes (PYG, sin decimales) e IVA 10 % / 5 % incluido en el precio.
- La base de la peluquería es `peluqueria` (admin / admin); se crea con
  `bash extra-addons/studio_bella/scripts/crear_peluqueria.sh`.
- Tests: `docker compose exec -T web odoo -c /etc/odoo/odoo.conf -d peluqueria -u studio_bella --test-enable --test-tags /studio_bella --stop-after-init --http-port=8079`
  (`--http-port=8079` porque el contenedor `web` ya usa el 8069).
- Cambios en Python: reiniciar con `docker compose restart web`. Cambios solo en XML o JS: alcanza con `-u studio_bella`.
- No borrar ni regenerar datos de una base que se esté usando: actualizar con `-u`.

## Cosas que no son obvias

- El plan contable genérico deja la moneda en USD al instalar Facturación: `configurar_base.py` la cambia a PYG.
- En Odoo 18 los precios de producto usan `min_display_digits`: para verlos sin decimales, `widget="monetary"`.
- Odoo guarda los archivos estáticos una semana en caché del navegador (por eso el manual se abre con `?v=`).
- En `<function>` de XML no se puede usar `eval` junto con hijos `<value>`.
- Validar entregas desde scripts necesita `with_context(skip_sms=True)`.
- Las secuencias de PostgreSQL (pedidos de compra, etc.) no se deshacen con los tests: pueden quedar saltos de número.
- El recordatorio por WhatsApp abre `wa.me` con el mensaje escrito (sin la API paga de WhatsApp Business), por decisión del usuario.
