# AutoFlow · Solicitudes del sitio web (`autoflow_sitio_web`)

Recibe el formulario de `sitio-web/contacto.html` y lo guarda en el CRM. Instalado en la base `autoflow_ventas`,
que atiende el servicio `ventas` de `docker-compose.yml` (http://localhost:8070).

## Cómo funciona

- `controllers/main.py`: ruta pública `POST /autoflow/solicitud` (`auth='public'`, `cors='*'`).
  Valida los datos, descarta lo que manda un robot (campo trampa `sitio_web`) y crea una oportunidad
  con la etiqueta "Sitio web", el medio "Website" y el detalle del formulario en la descripción.
- El aviso por correo usa la plantilla `mail_aviso_solicitud` (`data/crm_data.xml`) y va a la dirección del
  parámetro del sistema `autoflow_sitio_web.email_aviso`.
- Responde JSON: `{"ok": true}` o `{"ok": false, "errores": [...]}` con estado 400.

## Por qué una instancia aparte

Una petición sin sesión (como la del sitio) no puede elegir base: Odoo 18 solo la resuelve si el servidor
tiene una única base visible. Por eso el servicio `ventas` arranca con `--db-filter=^autoflow_ventas$`
y el Odoo de siempre (puerto 8069) sigue mostrando todas las bases.

## Pruebas

```bash
docker compose run --rm ventas odoo -d autoflow_ventas -u autoflow_sitio_web --test-enable --test-tags /autoflow_sitio_web --stop-after-init
```
