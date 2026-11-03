# Cuenta corriente en guaraníes y dólares (`cuenta_corriente`)

Módulo de Odoo 18 que muestra la cuenta corriente de cada cliente con el **Debe**, el **Haber** y el **saldo** en
guaraníes y en dólares, y la deja descargar en PDF. Depende solo de `account` (Facturación): las facturas, notas de
crédito y cobros se hacen con las pantallas de Odoo, en guaraníes o en dólares.

## Qué hace

- **Clientes** (*Cuenta corriente › Clientes*, la pantalla de inicio): cuánto debe cada cliente en guaraníes y en
  dólares, con el total abajo. El filtro *Con saldo pendiente* deja los que deben algo. En cada fila, **Movimientos**
  abre su cuenta y **Extracto PDF** baja su estado de cuenta.
- **Movimientos**: lo confirmado en las cuentas a cobrar, agrupado por cliente. Cada movimiento dice en palabras qué
  fue (*Tipo*: Factura, Cobro, Nota de crédito, Devolución de dinero o Ajuste por cotización; *Detalle*: "Cobro de
  la factura INV/2026/00001 · Banco en dólares"), en qué moneda se hizo, la cotización, el Debe y el Haber en Gs y en
  USD, y el **saldo que quedó después** en las dos monedas. Al pasar el mouse por el título de una columna se ve qué
  significa. Al tocar una línea se abre la factura o el cobro. Filtros: Facturas, Cobros, Notas de crédito,
  *Sin cancelar* y por fecha.
- **Extracto en PDF**: se elige el cliente y el período: "Desde" se carga con la fecha de su primer movimiento y
  "Hasta" con la de hoy, y las dos se pueden cambiar. Si en esas fechas no hay movimientos, avisa (con el saldo del
  cliente a esa fecha) en vez de bajar un PDF vacío. Sale en A4 apaisado con el saldo anterior, cada movimiento con
  su saldo, los totales, el saldo final en un recuadro y una explicación de cómo leerlo. También está en *Imprimir*
  de la ficha del cliente (ahí sale toda la cuenta hasta hoy, sin el aviso).
- **Factura y recibo de cobro** (los PDF de Odoo): debajo de los totales, un recuadro con el total en guaraníes y en
  dólares, el saldo a pagar si ya se pagó una parte, y la cotización usada. En el recibo, el monto recibido en las dos
  monedas.
- **De dólares a guaraníes**: lo que se hizo en dólares tiene su monto en USD, y en Gs con la cotización del día del
  movimiento: es el Debe y el Haber de la contabilidad de Odoo, que pasa cada factura y cada cobro a guaraníes con la
  cotización de su fecha. Lo que se hizo en guaraníes pasa a dólares con la cotización de ese día.
- **Ajustes por cotización**: si una factura en dólares se cobra otro día, con otra cotización, Odoo agrega al
  conciliar un movimiento de diferencia de cambio, solo en guaraníes (a veces con fecha de fin de mes, la del diario
  de diferencias de cambio). Con eso, cuando el cliente termina de pagar lo que debía en dólares, el saldo en
  guaraníes también queda en cero.
- **Ficha del cliente**: un botón con el saldo en Gs y en USD que abre sus movimientos, y otro para el extracto.
- **Cotización del dólar**: una por día, en guaraníes por cada dólar. Cada **30 minutos** Odoo trae la
  **referencial del BCP** (tarea programada *Cuenta corriente: cotización del dólar del BCP*; si Odoo estaba
  apagado, corre apenas se levanta): crea la de hoy al empezar el día y la corrige apenas el BCP publica otra. La
  columna *Origen* dice de dónde salió cada una: **BCP** (la trajo Odoo) o **A mano** (la cargó o la cambió
  alguien); la tarea no toca las de *A mano*. El botón **Traer la del BCP** (solo el administrador de Facturación)
  la trae en el momento y reemplaza la de hoy aunque sea *A mano*. Si un día no se carga, Odoo usa la última
  anterior.
- *Facturas* y *Cobros* llevan a las pantallas de Facturación. Para Excel, en *Movimientos* se marcan las líneas y
  se usa *Acciones › Exportar* de Odoo.

## Dónde está cada cosa

| Archivo | Para qué |
|---|---|
| `models/account_move_line.py` | `debe_usd`, `haber_usd`, `cotizacion`; tipo, detalle y saldo de cada movimiento; el dominio de la cuenta corriente |
| `models/res_partner.py` | `saldo_gs`, `saldo_usd`, el filtro *Con saldo pendiente*, los botones y los datos del extracto |
| `models/account_move.py` | Los montos en las dos monedas para la factura y el recibo |
| `models/res_currency_rate.py` / `data/cron.xml` | La cotización del BCP: la tarea diaria y el botón |
| `models/reporte_extracto.py` / `views/report_extracto.xml` | El extracto en PDF y su formato de papel |
| `wizard/extracto.py` / `views/extracto_views.xml` | El asistente que pide cliente y período |
| `views/report_dos_monedas.xml` | El recuadro en guaraníes y dólares de la factura y del recibo de Odoo |
| `views/res_partner_views.xml` | La lista de clientes con saldo y los botones de la ficha |
| `views/cuenta_corriente_views.xml` | La lista de movimientos, la búsqueda y la acción |
| `views/cotizacion_views.xml` | La lista de cotizaciones del dólar |

Debe Gs y Haber Gs son los campos `debit` y `credit` de Odoo: no se guardan dos veces. El tipo, el detalle y el
saldo se calculan al mostrarlos (no se guardan); el saldo cuenta toda la cuenta del cliente en orden de fecha,
aunque la lista esté filtrada.

## Decisiones

- **La cotización queda fija** al confirmar el movimiento, como hace Odoo con las facturas en dólares: si después
  se corrige la cotización de ese día, lo ya confirmado no cambia. Por eso conviene cargar la cotización del día
  antes de facturar.
- **El dólar de lo hecho en guaraníes es una equivalencia**: una factura en guaraníes cobrada en guaraníes otro día
  queda en cero en Gs, pero en USD puede quedar una diferencia chica por el cambio de cotización entre las dos
  fechas (Odoo no hace diferencia de cambio entre dos movimientos en guaraníes). El saldo que vale para la
  contabilidad es el de guaraníes; por eso *Con saldo pendiente* mira el saldo en guaraníes.
- **Montos sin símbolo en los PDF**: la columna dice si son guaraníes o dólares.
- **De dónde sale la cotización**: el usuario eligió la referencial diaria del BCP. Se toma de DolarPy
  (`https://dolar.melizeche.com/api/1.0/`, gratis y sin clave), que junta las del BCP, la SET y las casas de cambio;
  el BCP no tiene una API propia. Es la última publicada: a primera hora suele ser la del día hábil anterior. Si
  DolarPy no responde, la tarea lo anota en el log de Odoo y queda la cotización anterior; se puede cargar a mano.
- **Cada 30 minutos, a pedido del usuario**: la cotización de hoy puede cambiar durante el día cuando el BCP
  publica la nueva. Lo ya confirmado no cambia (Odoo deja fija la cotización al confirmar), así que dos facturas del
  mismo día pueden tener cotizaciones distintas: la columna *Cotización* de la cuenta corriente muestra la de cada
  una. Para cambiar cada cuánto corre: *Ajustes › Técnico › Automatización › Acciones planificadas* (con el modo desarrollador).

## Base de datos `cuenta_corriente`

Se crea desde cero con un solo comando, desde la carpeta del proyecto y con Odoo levantado:

```bash
bash extra-addons/cuenta_corriente/scripts/crear_cuenta_corriente.sh             # base "cuenta_corriente"
bash extra-addons/cuenta_corriente/scripts/crear_cuenta_corriente.sh otra_base   # con otro nombre
```

El script crea la base (español de Paraguay, `admin` / `admin`, sin los datos de demostración de Odoo), instala
`cuenta_corriente` y corre `scripts/configurar_base.py`, que pone la empresa en guaraníes con el IVA 10 % y 5 %
incluido (y "RUC" como nombre del documento fiscal), elige el diseño de los PDF, carga la cotización de hoy del BCP y
las de los últimos dos meses inventadas alrededor de ella (sin internet, alrededor de 7.370), un banco en dólares, y cinco clientes con facturas, una nota de crédito, cobros
en las dos monedas (completos y parciales), una factura en dólares pagada con guaraníes y un anticipo, con fechas
relativas al día de carga.

## Tests

```bash
bash scripts/pruebas.sh cuenta_corriente
```

Corren en la base `pruebas_cuenta_corriente`, no en `cuenta_corriente`. Después de cambiar código Python hay que
reiniciar Odoo: `docker compose restart web`.
