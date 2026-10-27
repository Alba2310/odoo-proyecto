# Studio Bella (`studio_bella`)

Sistema de la peluquería Studio Bella para Odoo 18. Depende de `account` (Facturación), `purchase_stock`
(Compras e Inventario) y `hr` (Empleados: los estilistas).

## Qué hace

- **Agenda** en calendario, con un color por estilista. Se cobra, se confirma o se cancela desde la cita.
- **Citas de hoy** en kanban por estado: Agendada → Confirmada → En atención → Cobrada.
- **Servicios** con precio (IVA incluido), duración e insumos. La duración de la cita sale de sus servicios.
- **Productos** de reventa (se venden en la cita o en el mostrador) y de uso profesional (insumos).
- **Cobro** en efectivo (con vuelto), tarjeta o transferencia: factura publicada, pago registrado y stock descontado.
- **Recordatorio** por correo al cliente el día antes de la cita (tarea programada diaria a las 10:00) y
  **por WhatsApp** con un clic desde *Recordatorios*: abre `wa.me` con el mensaje escrito (gratis, sin la API de
  WhatsApp Business; el mensaje sale del WhatsApp abierto en la computadora).
- **Compras**: pedidos a proveedores y recepción de mercadería con las pantallas de Compras e Inventario de Odoo,
  dentro del menú de Studio Bella. Cada producto tiene **stock mínimo** y "pedir hasta" (guardados en la regla de
  reabastecimiento de Odoo); cuando baja del mínimo aparece la actividad "Reponer stock", que se cierra sola al recibir.
- **Reportes**: servicios realizados por estilista y categoría; productos vendidos (análisis de facturas de Odoo).
- **Feriados y cierres**: pestaña agregada al horario de atención; esos días la agenda no da turnos.
- **Manual de usuario** dentro de Odoo: *Studio Bella › Ayuda › Manual de usuario*.

## Manual de usuario

Es una página HTML del módulo, [`static/manual/index.html`](static/manual/index.html), con capturas en
`static/manual/img/` (sacadas de los datos de ejemplo). Odoo la muestra dentro del sistema con la acción cliente
`studio_bella.manual` (`static/src/manual/`), que tiene botones para imprimirla y abrirla en otra pestaña.
También se puede abrir directo en http://localhost:8069/studio_bella/static/manual/index.html (el navegador la guarda
una semana en caché; desde el menú de Odoo siempre se ve la última versión).

## Dónde está cada cosa

| Modelo | Archivo | Para qué |
|---|---|---|
| `bella.cita` | `models/cita.py` | La cita: cliente, estilista, horario, servicios, productos y estado |
| `bella.cita.servicio` | `models/cita.py` | Servicio hecho en la cita; guarda estilista y fecha para el reporte |
| `bella.cita.producto` | `models/cita.py` | Producto vendido durante la cita |
| `bella.venta` / `bella.venta.linea` | `models/venta.py` | Venta de mostrador, sin cita |
| `bella.cobro.mixin` | `models/cobro.py` | Lo que comparten cita y venta al cobrar: factura, pago y stock (`AbstractModel`) |
| `bella.linea.producto` | `models/cobro.py` | Campos y cálculos comunes de las líneas de productos (`AbstractModel`) |
| `bella.servicio.insumo` | `models/producto.py` | Insumos que gasta cada servicio (tinte, oxidante, keratina...) |
| `bella.cobro.wizard` | `wizard/cobro_wizard.py` | Ventana de cobro: forma de pago, diario, efectivo recibido y vuelto |
| `product.template` | `models/producto.py` | Agrega la duración y los insumos del servicio, el stock mínimo y el aviso de reponer |
| `stock.picking` | `models/stock_picking.py` | Al validar una recepción o una salida, revisa los avisos de reponer |
| `hr.employee` | `models/hr_employee.py` | Agrega "Atiende en Studio Bella" y los servicios que hace cada estilista |
| `res.partner` | `models/res_partner.py` | Botón "Citas" en la ficha del cliente |

## Reglas de negocio

- **No se superponen citas** del mismo estilista (`_check_superposicion`). Las canceladas y las de clientes que
  no vinieron liberan el horario.
- **Solo dentro del horario del estilista** (`_check_horario`): usa el horario de trabajo del empleado de Odoo, con
  sus feriados y ausencias. Un estilista sin horario es "flexible" y se le puede agendar cuando sea.
- **El estilista tiene que hacer el servicio** (`_check_servicios_del_estilista`); si no tiene servicios cargados,
  hace todos.
- **A "Cobrada" solo se llega con el botón Cobrar** (no arrastrando la tarjeta), y una cita cobrada ya no cambia.
- **Stock al cobrar**: si falta un producto que se vende, no deja cobrar; si falta un insumo, cobra igual
  (el cliente ya fue atendido), el stock queda en negativo y se avisa en el historial de la cita.
- **Recordatorio**: si se cambia el horario o el estilista de la cita, se vuelve a mandar. El número de WhatsApp
  sale del celular o teléfono del cliente (`numero_whatsapp`: 0981 234 567 → 595981234567, con el código del país
  de la empresa).
- **Reponer stock**: la actividad se crea al cobrar, al validar movimientos y en una revisión diaria a las 7:00;
  no se duplica y se da por hecha cuando el stock vuelve a estar por encima del mínimo.
- La recepción no necesita permisos de Empleados: elige estilistas a través de `hr.employee.public`.

## Permisos

| Grupo | Puede |
|---|---|
| Studio Bella / Recepción | Agendar, vender, cobrar, mandar recordatorios y recibir mercadería (incluye Facturación y Usuario de Inventario) |
| Studio Bella / Administración | Además: pedidos a proveedores, servicios, productos, estilistas, reportes y borrar citas (incluye Administrador de Compras) |

## Base de datos `peluqueria`

Se crea desde cero con un solo comando, desde la carpeta del proyecto y con Odoo levantado:

```bash
bash extra-addons/studio_bella/scripts/crear_peluqueria.sh             # base "peluqueria"
bash extra-addons/studio_bella/scripts/crear_peluqueria.sh otra_base   # con otro nombre
```

El script hace tres pasos:
1. `scripts/crear_base.py` crea la base como el gestor de bases de Odoo: español de Paraguay, país Paraguay,
   usuario `admin` / `admin` y sin los datos de demostración de Odoo.
2. Instala `studio_bella` (`-i studio_bella --without-demo=all`).
3. Corre `scripts/configurar_base.py` con `odoo shell`.

`scripts/configurar_base.py` pone la empresa en guaraníes, crea el IVA 10 % y 5 % incluidos en el precio y carga
`demo/demo_data.xml` (14 servicios, 13 productos con stock, 4 estilistas, 12 clientes, citas de la semana pasada,
de hoy, de mañana y de la semana que viene, y los cobros de la semana pasada) y `demo/demo_compras.xml`
(2 proveedores, stock mínimo, un pedido recibido, uno confirmado esperando la recepción y uno en borrador).
Las fechas son relativas al día de carga.

Usuario: `admin` / `admin`.

## Tests

```bash
docker compose exec -T web odoo -c /etc/odoo/odoo.conf -d peluqueria -u studio_bella --test-enable --test-tags /studio_bella --stop-after-init --http-port=8079
```

Después de cambiar código Python hay que reiniciar Odoo: `docker compose restart web`.
