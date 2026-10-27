# AutoFlow ERP y Studio Bella · Odoo 18

Dos sistemas hechos sobre Odoo 18 Community, cada uno con su sitio web para venderlo: AutoFlow, para
concesionarias y talleres mecánicos, y Studio Bella, para peluquerías.

## Qué hay en el proyecto

| Carpeta | Contenido |
|---|---|
| `extra-addons/autoflow_management` | Módulo **AutoFlow ERP**: vehículos, pruebas de manejo, órdenes de servicio con kanban, repuestos, checklist de entrega, acta PDF con firma y análisis de fallas por modelo y por mecánico |
| `extra-addons/autoflow_sitio_web` | Recibe los formularios de contacto de los dos sitios y los guarda como oportunidades en el CRM ([detalle](extra-addons/autoflow_sitio_web/README.md)) |
| `extra-addons/studio_bella` | Módulo **Studio Bella** (peluquería): agenda de citas por estilista, servicios con insumos, venta de productos con stock, cobro con factura, recordatorios por correo y WhatsApp, compras y recepción de mercadería con stock mínimo, y manual de usuario ([detalle](extra-addons/studio_bella/README.md)) |
| `extra-addons/tienda_*` | Módulos de práctica: inventario, ventas y personal de una tienda |
| `extra-addons/mi_modulo` | Primer módulo de prueba |
| `sitio-web` | Sitio web de venta de AutoFlow ([detalle](sitio-web/README.md)) |
| `sitio-bella` | Sitio web de venta de Studio Bella, con demo interactiva ([detalle](sitio-bella/README.md)) |
| `presentacion` | Imágenes y gráficos de la presentación |
| `docker-compose.yml` | Odoo, PostgreSQL, el Odoo del CRM de ventas y los dos sitios web |

## Cómo levantarlo en otra computadora

Hace falta **Git** y **Docker**. En Windows: [Git para Windows](https://git-scm.com/download/win) y
[Docker Desktop](https://www.docker.com/products/docker-desktop/); los comandos se escriben en **Git Bash**.

1. Bajar el proyecto. El código de Odoo no está en el repositorio (pesa 1,3 GB), se descarga aparte:

   ```bash
   git clone https://github.com/Alba2310/odoo-proyecto.git
   cd odoo-proyecto
   git clone --depth 1 -b 18.0 https://github.com/odoo/odoo.git odoo-source
   ```

2. Levantar Odoo (la primera vez descarga las imágenes de Docker):

   ```bash
   docker compose up -d
   ```

3. Crear la base de la peluquería con sus datos de ejemplo (tarda unos minutos):

   ```bash
   bash extra-addons/studio_bella/scripts/crear_peluqueria.sh
   ```

4. Entrar a http://localhost:8069/web/login?db=peluqueria con usuario `admin` y contraseña `admin`.

| Servicio | Dirección |
|---|---|
| Odoo | http://localhost:8069 |
| CRM de ventas del sitio | http://localhost:8070 |
| Sitio web de AutoFlow | http://localhost:5500 |
| Sitio web de Studio Bella | http://localhost:5501 |

Las bases de datos viven en los volúmenes de Docker y **no se suben a GitHub**: en cada computadora se crean de nuevo.
Para AutoFlow, crear una base desde http://localhost:8069 e instalar el módulo **AutoFlow ERP** en Aplicaciones.

Para llevarse una base con todos sus datos tal como están: en la computadora de origen, entrar a
http://localhost:8069/web/database/manager y usar **Backup** (descarga un .zip); en la otra, **Restore** con ese
archivo. Las dos operaciones piden la contraseña maestra de Odoo.
