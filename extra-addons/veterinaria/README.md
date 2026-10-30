# Patitas (`veterinaria`)

Sistema para veterinarias en Odoo 18. Depende de `account` (Facturación), `purchase_stock` (Compras e
Inventario) y `hr` (Empleados: los veterinarios y peluqueros).

Está pensado para venderlo a cualquier veterinaria: no tiene datos de una en particular. El nombre técnico es
`veterinaria`; el producto se llama **Patitas**.

## Qué hace

- **Hoy en Patitas** (*Patitas › Hoy*, la pantalla de inicio): el tablero de la recepción. La sala de espera en
  cuatro columnas (turnos de hoy → sala de espera → en atención → para retirar y cobrar), con la foto o el dibujo de
  la mascota, el tiempo que lleva esperando, las alertas ("muerde") y los botones de cada paso. Abajo, los internados
  y hospedados (en rojo si pasaron más de 8 horas sin control). Arriba, las vacunas para avisar, los productos para
  reponer, los turnos de mañana y lo cobrado hoy. Se filtra por área y se actualiza solo cada minuto. Las tarjetas
  se **arrastran** de una columna a otra (con el mouse o con el dedo): hacia adelante hace lo mismo que el botón de
  ese paso, hacia atrás lo deshace (`vet.atencion.action_mover`).
- **Mascotas**: cada una con su dueño, especie, raza, sexo, edad (sale de la fecha de nacimiento), microchip,
  alertas, alergias y foto. La ficha tiene una **línea de tiempo** con todo lo que se le hizo (consultas, vacunas,
  baños, internaciones) y el **gráfico de su peso**. Se imprimen el **carnet de vacunas** y la **historia clínica**.
- **Atención**: el turno de la agenda (consultorio o baño y peluquería) o la mascota que llegó sin turno. Lleva lo
  que se hizo y se vendió, la **historia clínica** (lo que cuenta el dueño, signos, examen, diagnóstico, tratamiento,
  indicaciones para la casa, próximo control) y, en la peluquería, lo que pidió el dueño y lo que encontraron. Las
  indicaciones se imprimen con la firma y matrícula del veterinario. Desde una consulta se **interna** con un botón.
- **Vacunas y desparasitaciones**: un producto marcado como vacuna o antiparasitario, con "próxima dosis a los N
  días". Al terminar la atención queda anotado en el carnet (con el lote) y se calcula la próxima dosis.
  *Mascotas › Vacunas para avisar* junta las que vencen; el botón **WhatsApp** le escribe al dueño con **todas las
  dosis de todas sus mascotas en un solo mensaje**. Unos días antes (7, se cambia en Ajustes) le llega un correo.
- **Baño y peluquería**: agenda propia y el aviso "ya está listo y perfumado, podés pasar a retirarlo" por WhatsApp,
  con lo que se encontró (pulgas, nudos).
- **Internación y hotel**: lugares (jaulas, caniles, gateras) con el mapa de quién está en cada uno, reservas del
  hotel con fecha de entrada y salida, controles (temperatura, peso, ánimo, si comió, medicación), el **parte por
  WhatsApp** con el último control, la medicación y los extras, la constancia de ingreso para firmar y el cobro
  **por día**.
- **Cobro con factura y pago mixto**: en efectivo, tarjeta, transferencia o QR, o una parte con cada uno. Se emite la
  factura, se registra un pago por forma de pago (cada una en su diario) y se calcula el vuelto.
- **Venta de mostrador**: alimentos, pipetas y accesorios sin atender a la mascota.
- **Stock y compras**: los productos con stock se descuentan al cobrar. Cada uno tiene stock mínimo y "pedir hasta";
  los que bajan del mínimo aparecen en *Compras › Para reponer* (la pantalla de Reabastecimiento de Odoo), desde donde
  se pide al proveedor. Pedidos a proveedores y recepción de mercadería con las pantallas de Odoo.
- **Turnos por internet**: una página pública (`/reservar`) que funciona como un chat: el dueño cuenta cómo se llama
  su mascota, qué es, qué necesita (solo se ofrece lo que es para esa especie), con quién y cuándo, y deja sus datos.
  El turno entra a la agenda y la mascota y el dueño se reconocen solos (por el celular y el nombre) o se crean.
- **Recordatorio del turno** por correo el día antes (tarea diaria a las 10:00) y por WhatsApp con un clic.
- **Reportes**: lo que se hizo y vendió en las atenciones por área, profesional, especie y mes; facturación de Odoo.

Los mensajes de WhatsApp abren `wa.me` con el texto escrito (gratis, sin la API paga de WhatsApp Business): falta
tocar Enviar en el WhatsApp abierto en la computadora.

## Dónde está cada cosa

| Modelo | Archivo | Para qué |
|---|---|---|
| `vet.mascota` | `models/mascota.py` | La mascota; `vet_linea_tiempo` arma la línea de tiempo y el gráfico del peso |
| `vet.especie` / `vet.raza` | `models/especie.py`, `data/especies.xml` | Especies (con su dibujo) y razas |
| `vet.peso` | `models/peso.py` | Cada pesada; `vet.registra.peso` la anota desde la atención y el control |
| `vet.atencion` / `vet.atencion.linea` | `models/atencion.py` | Turno, recorrido, historia clínica, peluquería y lo que se cobra |
| `vet.aplicacion` | `models/aplicacion.py` | Vacuna o desparasitación aplicada, próxima dosis y avisos |
| `vet.internacion` / `vet.internacion.linea` / `vet.control` / `vet.lugar` | `models/internacion.py` | Internación y hotel |
| `vet.venta` / `vet.venta.linea` | `models/venta.py` | Venta de mostrador |
| `vet.cobrable` / `vet.linea.venta` | `models/cobro.py` | Lo común al cobrar: factura, pagos, stock, líneas que no cambian después de cobrar |
| `vet.cobro.wizard` | `wizard/cobro_wizard.py` | La caja: reparte el total entre las formas de pago y calcula el vuelto |
| `vet.tablero` | `models/tablero.py`, `static/src/tablero/` | Los datos y la pantalla de "Hoy en Patitas" (OWL) |
| — | `static/src/ficha/` | El widget `vet_linea_tiempo` de la ficha de la mascota (OWL) |
| `vet.reserva` | `models/reserva.py`, `controllers/reserva.py`, `static/reserva/` | La página `/reservar` |
| `product.template` | `models/producto.py` | Área, duración, reserva por internet, especies, vacuna/antiparasitario, stock mínimo |
| `hr.employee` | `models/hr_employee.py` | "Atiende en Patitas", matrícula y servicios que hace |
| `res.company` / `res.config.settings` | `models/res_company.py` | Página de turnos, avisos, controles, precio por día y diarios de cada pago |

## Reglas de negocio

- **Turnos**: no se pisan los del mismo profesional; solo dentro de su horario de trabajo (con feriados y ausencias);
  el profesional tiene que atender en esa área y, si tiene servicios cargados, hacer esos. Una vacuna no es un
  servicio: la aplica cualquiera del consultorio. Los que **llegan sin turno** no ocupan la agenda ni necesitan
  profesional hasta que se los atiende (los atiende quien aprieta "Atender", si es del área).
- **Recorrido**: Turno reservado → En sala de espera → En atención → Terminada → Cobrada. Se guarda a qué hora llegó,
  la atendieron y terminó. Arrastrar una tarjeta hacia atrás borra esas horas y, si deja de estar terminada, lo que
  se anotó en el carnet (se vuelve a anotar al terminar); quien llegó sin turno no vuelve a "Turnos de hoy". A
  "Cobrada" solo se llega con el botón Cobrar, y cobrada ya no cambia (tampoco sus líneas,
  `vet.linea.venta`).
- **Carnet**: al terminar (o al cobrar, si no se terminó) cada línea con una vacuna o antiparasitario se anota una
  sola vez, con la fecha del turno, el lote y quien la aplicó. La próxima dosis se puede corregir a mano (los
  cachorros, cada tres semanas). Una dosis nueva del mismo producto "renueva" la anterior, que deja de avisarse.
- **Avisos de vacunas**: el WhatsApp junta las dosis del dueño que vencen en los próximos 30 días o ya vencieron. El
  correo sale una vez por dosis, unos días antes; si se cambia la fecha, se vuelve a avisar. No se avisa de las
  mascotas fallecidas ni de las dosis marcadas "No avisar más".
- **Cobro**: los pagos tienen que sumar el total. Lo que no se paga con tarjeta ni transferencia queda en efectivo.
  Si el total de la factura no coincide con el de la atención (un producto con el IVA sin incluir), no se cobra.
  Si falta stock de algo que se vende, no se cobra; en la internación sí (los remedios ya se usaron) y se avisa que
  quedó en negativo.
- **Internación y hotel**: una mascota por lugar; las reservas del hotel tampoco se pisan. Los días se cuentan del
  día de ingreso al de salida, como mínimo uno, y se pueden corregir antes de cobrar. Solo se cargan controles de
  las mascotas que están adentro.
- **Página de turnos**: horarios cada 30 minutos, con una hora de anticipación y hasta 14 días adelante (constantes al
  principio de `models/reserva.py`). Servicios de una sola área por turno. Hasta 3 turnos pendientes por dueño, y un
  campo oculto frena a los robots.

## Permisos

| Grupo | Puede |
|---|---|
| Patitas / Personal | Dar turnos, atender, cargar la historia clínica y el carnet, internar y cargar controles, vender, cobrar, mandar avisos (incluye Facturación y Usuario de Inventario) |
| Patitas / Administración | Además: servicios, productos, profesionales, lugares, especies, compras, reportes, ajustes y borrar (incluye Administrador de Compras y Empleados) |

## Base de datos `veterinaria`

Se crea desde cero con un solo comando, desde la carpeta del proyecto y con Odoo levantado:

```bash
bash extra-addons/veterinaria/scripts/crear_veterinaria.sh             # base "veterinaria"
bash extra-addons/veterinaria/scripts/crear_veterinaria.sh otra_base   # con otro nombre
```

El script crea la base (español de Paraguay, `admin` / `admin`, sin los datos de demostración de Odoo), instala
`veterinaria` y corre `scripts/configurar_base.py`, que pone la empresa en guaraníes con el IVA 10 % y 5 % incluido y
carga una veterinaria de ejemplo con fechas relativas al día de carga: 30 servicios y productos, 4 profesionales,
8 lugares, 10 dueños con 13 mascotas y su historia, un perro internado, una perra en el hotel, la sala de espera de
hoy, turnos de mañana, ventas de mostrador y dos pedidos a proveedores. Las tasas de IVA de los productos de ejemplo
(5 % en vacunas y farmacia) son de muestra: cada veterinaria las confirma con su contador.

## Tests

```bash
bash scripts/pruebas.sh veterinaria
```

Corren en la base `pruebas_veterinaria`, no en `veterinaria`. Después de cambiar código Python hay que reiniciar
Odoo: `docker compose restart web patitas`.

## Página de turnos

Odoo tiene que saber de qué base son los turnos sin que el dueño inicie sesión. En el servidor de la veterinaria, con
una sola base (o con `--db-filter`), la página es la dirección de Odoo seguida de `/reservar`. En este proyecto la
atiende el servicio `patitas` de `docker-compose.yml` (un Odoo con `--db-filter=^veterinaria$`):
**http://patitas.localhost:8073/reservar**. Tiene nombre propio para no compartir la sesión con los otros Odoo.
