# Solicitudes de los sitios web (`autoflow_sitio_web`)

Recibe los formularios de `sitio-web/contacto.html` (AutoFlow) y `sitio-bella/contacto.html` (Studio Bella)
y los guarda en el mismo CRM. Estaba instalado en la base `autoflow_ventas`, que atendía el servicio `ventas`
de `docker-compose.yml` (http://localhost:8070). Los dos se quitaron el 28/10/2026: hoy no está instalado.
Para volver a usarlo, restaurar el respaldo de esa base y volver a agregar el servicio (está en el historial de git).

## Cómo funciona

- `controllers/main.py`: ruta pública `POST /autoflow/solicitud` (`auth='public'`, `cors='*'`).
  Valida los datos, descarta lo que manda un robot (campo trampa `sitio_web`) y crea una oportunidad
  con la etiqueta "Sitio web", la del producto, el medio "Website" y el detalle del formulario en la descripción.
- El campo `producto` dice de qué sitio viene: `studio_bella` o, si no viene, `autoflow`. Cada producto tiene
  sus tipos de negocio y sus planes (`PRODUCTOS` en `controllers/main.py`).
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
