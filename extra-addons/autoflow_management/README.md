# AutoFlow ERP (`autoflow_management`)

Concesionario y taller para Odoo 18. Depende de `sale_crm` (Ventas + CRM), `sale_stock` (Inventario),
`account` (Facturación) y `hr` (empleados: mecánicos y responsables de pruebas de manejo).

## Dónde está cada cosa

### Fase 1: modelos y relaciones

| Modelo | Archivo | Relaciones principales |
|---|---|---|
| `autoflow.vehicle` | `models/vehicle.py` | Many2one a modelo/marca y propietario (`res.partner`); One2many a fotos, pruebas, órdenes y cotizaciones |
| `autoflow.vehicle.brand` / `.model` | `models/vehicle.py` | El modelo pertenece a una marca |
| `autoflow.vehicle.photo` | `models/vehicle.py` | Galería de fotos del vehículo (`image.mixin`) |
| `autoflow.test.drive` | `models/test_drive.py` | Cliente, oportunidad (`crm.lead`), vehículo y responsable (`hr.employee`) |
| `autoflow.workshop.order` | `models/workshop_order.py` | Cliente, vehículo, mecánico, depósito (`stock.warehouse`), factura (`account.move`), daños (Many2many) |
| `autoflow.workshop.part.line` | `models/workshop_order.py` | Repuestos (`product.product`) y su movimiento de stock (`stock.move`) |
| `autoflow.workshop.labor.line` | `models/workshop_order.py` | Horas de mano de obra por mecánico |
| `autoflow.inspection.line` | `models/inspection.py` | Detalle del checklist de entrega (maestro: la orden de servicio) |
| `autoflow.inspection.item` / `autoflow.damage.type` | `models/inspection.py` | Catálogos: puntos a revisar y daños visibles |

El catálogo de repuestos de taller (aceites, filtros, frenos, rulemanes, suspensión, motor y eléctrico) son productos
de Odoo en la categoría "Repuestos de taller" (`data/workshop_parts_data.xml`); se ven en AutoFlow › Taller › Repuestos.
El stock inicial de ejemplo está en `demo/workshop_parts_stock.xml`.

### Fase 2: lógica de negocio

- **`@api.constrains`**: `AutoflowTestDrive._check_vehicle_available` rechaza vehículos en mantenimiento o vendidos;
  `_check_overlap` evita que un vehículo tenga dos pruebas a la misma hora. También se validan el VIN, las fechas,
  el kilometraje y que un vehículo no tenga dos órdenes abiertas.
- **`@api.depends`**: `AutoflowWorkshopOrder._compute_amounts` suma mano de obra y repuestos; las líneas calculan
  su subtotal y toman el precio del producto.
- **`@api.onchange`**: al elegir el vehículo en la orden, en la prueba de manejo o en la recepción se proponen
  el cliente y el kilometraje.
- **Kilometraje**: `AutoflowVehicle._update_odometer` se llama al finalizar una prueba de manejo y una orden.
- **Workflow**: `AutoflowWorkshopOrder.write` detecta el cambio de etapa (botón, barra de estado o arrastre en el kanban):
  - *Listo para entrega*: envía la plantilla `mail_template_vehicle_ready` al cliente y crea una actividad para el asesor.
  - *Finalizado*: valida mecánico, checklist y stock; descuenta los repuestos con movimientos de stock, actualiza
    el kilometraje, devuelve el vehículo a su estado anterior y crea la factura en borrador
    (las órdenes en garantía no se facturan al cliente).
- **Ventas**: desde una prueba de manejo finalizada se crea la cotización; al confirmarla el vehículo queda vendido.

### Fase 3: interfaz

- Kanban de órdenes agrupado por etapa (`views/workshop_order_views.xml`); `group_expand` muestra todas las columnas.
- Calendario de pruebas de manejo (`views/test_drive_views.xml`).
- Asistente de recepción (`wizard/`), con el widget propio `fuel_slider` (`static/src/fuel_slider/`, componente OWL)
  y los daños con `many2many_checkboxes`.

### Fase 4: reportes

- PDF "Orden de servicio y acta de entrega" con logo, repuestos, costos y firma: `report/workshop_order_report.xml`.
  La firma se captura en la pestaña *Acta de entrega* de la orden.
- Análisis (menú AutoFlow › Análisis, `views/analysis_views.xml`): fallas por modelo (órdenes correctivas) y
  órdenes cerradas por mecánico en el mes.

## Permisos

- **AutoFlow / Usuario**: opera vehículos, pruebas y órdenes. Incluye vendedor y usuario de inventario.
- **AutoFlow / Responsable**: además ve costos de adquisición, análisis y configuración.

La factura se crea con `sudo()`, así quien entrega el vehículo no necesita permisos de facturación.

## Pruebas

```bash
bash scripts/pruebas.sh autoflow_management
```

Corren en la base `pruebas_autoflow_management` (el script la crea la primera vez), no en `autoflow_py`, para que
los números de órdenes y facturas de la base real no queden salteados.
