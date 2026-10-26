# AutoFlow ERP · Odoo 18

Sistema para concesionaria y taller mecánico hecho sobre Odoo 18 Community, más el sitio web para venderlo.

## Qué hay en el proyecto

| Carpeta | Contenido |
|---|---|
| `extra-addons/autoflow_management` | Módulo **AutoFlow ERP**: vehículos, pruebas de manejo, órdenes de servicio con kanban, repuestos, checklist de entrega, acta PDF con firma y análisis de fallas por modelo y por mecánico |
| `extra-addons/autoflow_sitio_web` | Recibe el formulario de contacto del sitio y lo guarda como oportunidad en el CRM ([detalle](extra-addons/autoflow_sitio_web/README.md)) |
| `extra-addons/tienda_*` | Módulos de práctica: inventario, ventas y personal de una tienda |
| `extra-addons/mi_modulo` | Primer módulo de prueba |
| `sitio-web` | Sitio web de venta de AutoFlow ([detalle](sitio-web/README.md)) |
| `presentacion` | Imágenes y gráficos de la presentación |
| `docker-compose.yml` | Odoo, PostgreSQL, el Odoo del CRM de ventas y el sitio web |

## Cómo levantarlo

Hace falta Docker. El código de Odoo no está en el repositorio (pesa 1,3 GB), se descarga aparte:

```bash
git clone https://github.com/Alba2310/odoo-proyecto.git
cd odoo-proyecto
git clone --depth 1 -b 18.0 https://github.com/odoo/odoo.git odoo-source
docker compose up -d
```

| Servicio | Dirección |
|---|---|
| Odoo | http://localhost:8069 |
| CRM de ventas del sitio | http://localhost:8070 |
| Sitio web | http://localhost:5500 |

Las bases de datos viven en los volúmenes de Docker y no se suben: en una instalación nueva hay que crear la base
desde http://localhost:8069 e instalar el módulo **AutoFlow ERP** en Aplicaciones.
