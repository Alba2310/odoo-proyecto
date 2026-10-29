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
- **Turnos por internet**: página pública `/turnos` (sin usuario) donde la clienta elige servicios, estilista
  (o "cualquiera"), día y hora libres, y deja nombre y celular. El turno entra a la agenda como Agendada con
  `origen = internet`; la recepción los ve en *Turnos por internet › Turnos pedidos* y los confirma. Si nadie hace
  todos los servicios elegidos (un corte y una manicura), con "cualquiera" se reservan uno detrás del otro: una cita
  por tramo, cada una con quien lo hace (`bella.turnos._tramos`).
- **Cierre de caja** del día: lo cobrado en efectivo, tarjeta y transferencia (según la fecha de la factura),
  arqueo del efectivo (cambio al abrir + efectivo cobrado − salidas = tiene que haber; contado − eso = diferencia),
  lo que queda de cambio y lo que se retira. Se imprime y, cerrado, no deja cobrar con esa fecha.
- **Clientas que no vuelven** (*Clientes › Clientas que no vuelven*): las que hace más de 6 semanas (o 3 o 6 meses)
  no vienen y no tienen turno pedido, con su última visita, cuántas veces vinieron y cuánto gastaron. El botón
  **Invitar** abre `wa.me` con un mensaje que las invita a volver, el enlace de la página de turnos y sus puntos.
- **Ficha técnica**: en cada cita se anota el trabajo (color, mechas, alisado...) con la fórmula, el tiempo de pose,
  el resultado y una foto; la cita muestra los trabajos anteriores de la clienta. Las **alergias** de la clienta
  aparecen en rojo arriba de cada cita.
- **Comisiones** (*Studio Bella › Comisiones*, Administración): cada estilista tiene un % por servicios y otro por
  productos. La liquidación junta sus citas cobradas en el período (cuenta el día del cobro, como el cierre de caja),
  descuenta adelantos, se imprime para firmar y se marca pagada. Cada servicio entra en una sola liquidación.
- **Programa de puntos** (se activa en *Configuración › Ajustes*): 1 punto cada 10.000 Gs. pagados y cada punto vale
  500 Gs. de descuento (los dos montos se cambian). Los puntos se usan en la ventana de cobro.
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
| `bella.turnos` | `models/turnos.py` | Turnos por internet: horarios libres, reserva y datos de la página (`AbstractModel`) |
| — | `controllers/turnos.py` | Rutas públicas `/turnos`, `/turnos/horarios` y `/turnos/reservar` |
| — | `views/turnos_templates.xml`, `static/turnos/` | La página de turnos (QWeb, CSS y JS sin dependencias) |
| `bella.cierre.caja` | `models/cierre_caja.py` | Cierre de caja del día, con su comprobante imprimible |
| `product.template` | `models/producto.py` | Agrega la duración y los insumos del servicio, el stock mínimo y el aviso de reponer |
| `stock.picking` | `models/stock_picking.py` | Al validar una recepción o una salida, revisa los avisos de reponer |
| `bella.ficha.tecnica` | `models/ficha_tecnica.py` | Trabajo hecho a la clienta: fórmula, tiempo de pose, resultado y foto |
| `bella.liquidacion.comision` | `models/comision.py` | Comisiones de una estilista en un período, con su comprobante imprimible |
| `bella.puntos` | `models/puntos.py` | Movimientos de puntos de una clienta (ganados, usados o regalados) |
| `hr.employee` | `models/hr_employee.py` | Agrega "Atiende en Studio Bella", los servicios que hace y sus % de comisión |
| `res.partner` | `models/res_partner.py` | Botones "Citas" y "Puntos", pestaña Studio Bella (visitas, alergias, fichas) e invitación a volver |
| `res.company` / `res.config.settings` | `models/res_company.py` | Programa de puntos y dirección de la página de turnos (*Configuración › Ajustes*) |

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
- **Turnos por internet**: los horarios libres salen de `_work_intervals_batch` del horario de cada estilista
  (feriados y ausencias incluidos) menos sus citas, cada 30 minutos, con una hora de anticipación y hasta 14 días
  adelante (constantes al principio de `models/turnos.py`). Al reservar se vuelve a calcular y valen las mismas
  restricciones de la cita. La clienta se reconoce por el celular (`numero_whatsapp`); si no existe, se crea.
  Hasta 3 turnos pendientes por clienta, y un campo oculto frena a los robots. Solo se ofrecen los servicios con
  "Se reserva por internet" (`bella_reserva_online`). Servicios de distintas estilistas: los servicios se juntan, en
  el orden en que se eligieron, en tramos que puede hacer una sola estilista; un horario sirve si cada tramo tiene
  alguien libre justo cuando termina el anterior (esos tramos se buscan cada 5 minutos).
- **Cierre de caja**: uno por día. Los totales se recalculan con cada cobro de ese día mientras está abierto;
  cerrado, `_bella_cobrar` no deja cobrar con esa fecha y solo Administración lo reabre.
- **Clientas que no vuelven**: la última visita (`bella_ultima_visita`, guardada) es el día de la última cita
  cobrada; las ventas de mostrador no cuentan. "Sin turno pedido" busca citas agendadas o confirmadas desde ahora.
- **Comisiones**: sobre el precio cobrado con IVA incluido de los servicios y productos de las citas de la
  estilista (las ventas de mostrador no tienen estilista). El descuento por puntos lo absorbe la peluquería. Entra lo
  cobrado en el período según la fecha de la factura: una cita que se cobra después de pagar la liquidación de su día
  entra en la siguiente. No entran las citas con la factura anulada entera por notas de crédito. Los porcentajes salen
  de la estilista al crear la liquidación y quedan fijos en ella. Pagada, no se modifica ni se borra.
- **Líneas cobradas**: los servicios y productos de una cita o venta cobrada no se pueden cambiar ni borrar, tampoco
  por fuera de la pantalla (`bella.linea.cobrada`), y solo Administración ve y mueve `liquidacion_id`.
- **Puntos**: se ganan sobre lo que se pagó (sin lo pagado con puntos) y nunca para "Consumidor final". Al usarlos,
  el descuento entra en la factura como una línea negativa por cada tasa de IVA, en proporción a lo que suma cada una,
  así el IVA queda calculado sobre lo cobrado. No se usan más puntos de los que hay ni más descuento que el total.
  Los puntos no vencen y una nota de crédito no los devuelve: si hace falta, se corrigen a mano en *Clientes › Puntos*.
  Cada compañía tiene su propio saldo (`_bella_saldo_puntos`), y al usarlos se bloquea a la clienta hasta el final del
  cobro para que dos cajas no gasten los mismos puntos. Las visitas y lo gastado, en cambio, cuentan todas las compañías.
- **Ficha técnica**: la clienta, la estilista, el día y la compañía salen de la cita y la siguen si se corrige.

## Permisos

| Grupo | Puede |
|---|---|
| Studio Bella / Recepción | Agendar, vender, cobrar (y usar puntos), mandar recordatorios e invitaciones, cargar fichas técnicas, confirmar turnos pedidos por internet, cerrar la caja y recibir mercadería (incluye Facturación y Usuario de Inventario) |
| Studio Bella / Administración | Además: reabrir una caja cerrada, comisiones, cargar puntos a mano, pedidos a proveedores, servicios, productos, estilistas, reportes y borrar citas y fichas (incluye Administrador de Compras) |

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
(2 proveedores, stock mínimo, un pedido recibido, uno confirmado esperando la recepción y uno en borrador) y
`demo/demo_clientas.xml` (programa de puntos activo, % de comisión de cada estilista, alergias, fichas técnicas,
4 clientas que no vienen hace 8 a 20 semanas y una liquidación de comisiones por pagar), y cierra la caja de los días
de esos cobros (uno con un faltante de 10.000). Las fechas son relativas al día de carga.

Usuario: `admin` / `admin`.

## Tests

```bash
bash scripts/pruebas.sh studio_bella
```

Corren en la base `pruebas_studio_bella` (el script la crea la primera vez), no en `peluqueria`: los tests deshacen
lo que crean, pero no los números de las citas y facturas, que en la base real quedarían salteados.

Después de cambiar código Python hay que reiniciar Odoo: `docker compose restart web turnos`.

## Página de turnos

Odoo tiene que saber de qué base son los turnos sin que la clienta inicie sesión. En el servidor de la peluquería,
con una sola base (o con `--db-filter`), la página es la dirección de Odoo seguida de `/turnos`.
En este proyecto, que tiene varias bases, la atiende el servicio `turnos` de `docker-compose.yml` (un Odoo con
`--db-filter=^peluqueria$`): **http://127.0.0.1:8071/turnos**. Se usa 127.0.0.1 y no localhost para que no
comparta la sesión con el Odoo del puerto 8069. Desde Odoo, *Turnos por internet › Página para las clientas*
abre `/turnos` en el mismo servidor (funciona porque la sesión ya está en la base `peluqueria`).
