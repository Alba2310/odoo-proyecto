# Óga · control de alquileres (`alquileres`)

Sistema para el dueño o el administrador de viviendas en alquiler: casas y edificios, contratos, cobros con aviso
por WhatsApp, gastos y ganancia, mantenimiento, actas de entrega y una página pública "Se alquila".
Base `alquileres` (admin / admin). "Óga" es "casa" en guaraní; el nombre técnico del módulo sigue siendo
`alquileres`.

## Cómo se usa

1. **Configuración › Propiedades**: una casa se alquila entera (su unidad se crea sola); en un edificio se carga un
   departamento por unidad. En cada unidad, la foto y los datos para la página "Se alquila".
2. **Contratos › Contratos › Nuevo**: unidad, inquilino (con su WhatsApp), alquiler, día de pago, depósito, fechas y
   reajuste anual. **Activar contrato** crea las cuotas; **Imprimir para firmar** saca el contrato en PDF
   (es un modelo: conviene que lo revise un abogado).
3. **Panel** (la pantalla de inicio): cobrado del mes, deuda, ocupación, ganancia, gráfico de los últimos meses y
   lo que hay que atender (avisos, contratos que vencen, reajustes, reparaciones, interesados).
4. **Avisos de hoy**: los inquilinos a los que toca avisar; el botón de WhatsApp abre el mensaje ya escrito.
5. **Registrar pago** en la cuota e **Imprimir recibo**. Los cargos extra (ANDE, agua, reparaciones) se agregan en
   la cuota y se cobran junto con el alquiler. Cada cuota paga un mes de pago, del día de pago al día anterior del
   mes siguiente (se paga por adelantado). Si el contrato empieza o termina a mitad de uno, esa cuota es
   proporcional a los días que el inquilino vive ahí: se llama, por ejemplo, "Enero 2025 (16 de 31 días)" y el
   recibo lo aclara. Si entra antes del día de pago, esos primeros días son del mes de pago anterior.
6. **Cobros y gastos › Gastos**: lo que gasta el dueño en cada propiedad. **Reportes › Ganancia por propiedad**.
7. **Mantenimiento**: pedidos de reparación. Al resolverlos, el costo va a los gastos y, si lo paga el inquilino,
   también a su cuota (el dueño le paga al que lo arregla y después lo cobra: así la ganancia cuadra).
8. **Contratos › Actas de entrega**: estado de la unidad al entrar y al salir, con fotos, medidores y llaves.
9. **Terminar contrato**: el depósito paga lo que quedó debiendo, se descuentan los daños y queda lo que hay que
   devolver. Si el inquilino se va más adelante, hasta ese día el contrato sigue vigente (se cobran sus cuotas y la
   unidad sigue alquilada) y al día siguiente se termina solo. **Renovar** extiende el contrato; el alquiler nuevo
   rige desde que empieza la renovación (las cuotas que faltan del plazo actual siguen con el de ahora). Si el
   contrato terminaba a mitad de un mes de pago, esa cuota pasa a cobrar también los días de la renovación, con el
   alquiler nuevo, sin cobrar dos veces los mismos días.
10. **Se alquila › Interesados**: los que dejaron sus datos en la página pública. **Ver la página** la abre.

## Cómo funciona

- `models/contrato.py`: `_generar_cuotas` crea una cuota por mes hasta las que vencen en los próximos 10 días; el
  cron de las 6:00 primero aplica los reajustes y los alquileres de las renovaciones que llegaron
  (`_aplicar_reajustes`), termina los contratos cuyo día de salida (`fecha_salida`) ya pasó y después crea las
  cuotas. Las cuotas que vencen desde la fecha de reajuste o de renovación ya salen con el monto nuevo
  (`_monto_para`). El primer reajuste se propone al año de empezar o, si el contrato empezó hace más de un año, en
  el próximo aniversario: el alquiler que se carga es el de ahora. Meses parciales: `_periodo` da el mes de pago
  de cada cuota, `_cuotas_por_crear` calcula la proporción (`dias` de `dias_periodo`, redondeado a guaraníes) y
  `_ajustar_cuota_del_fin` vuelve a calcular la cuota del mes en que termina cuando cambia la fecha de fin (al
  terminar o renovar; al terminar no baja de lo que ya se pagó). `_terminar` usa el depósito para pagar las cuotas
  pendientes (pagos con medio "Del depósito de garantía") y guarda el descuento por daños. Las cláusulas del
  contrato impreso salen de `_clausulas()`.
- `models/cuota.py`: total = alquiler + cargos extra; estado (pendiente, pago parcial, pagada) según los pagos.
  Avisos: `proximo_aviso` arranca 3 días antes de vencer y después de cada aviso pasa al día del vencimiento o a 3
  días después. `calificar()` da el puntaje de cómo paga el inquilino (a tiempo = hasta 3 días después de vencer).
- WhatsApp: abre `wa.me` con el texto (gratis, sin la API de WhatsApp Business), igual que Studio Bella.
- `models/resultado.py`: vista SQL con lo cobrado y los gastos, para la ganancia. El depósito no es ingreso
  cuando se cobra ni cuando se devuelve; lo que se usa al terminar sí, el día que se usa: las cuotas que se pagan
  con él y el descuento por daños que se retiene.
- `models/panel.py` + `static/src/panel/`: los datos y la pantalla del Panel (acción de cliente en OWL).
- `controllers/se_alquila.py` + `views/se_alquila_templates.xml` + `static/se_alquila/`: la página pública. Como
  toda ruta pública, necesita un Odoo con una sola base: el servicio `oga` de docker-compose (puerto 8072,
  `--db-filter=^alquileres$`), en http://se-alquila.localhost:8072/se-alquila. El botón "Consultar" escribe al
  teléfono de la empresa (Ajustes); la dirección que abre "Ver la página" está en el parámetro
  `alquileres.url_pagina`.
- Grupos: **Encargado de cobros** (registra pagos, cargos y avisos, carga reparaciones y actas) y
  **Administrador** (además propiedades, contratos, gastos y reportes). Con varias empresas, cada una ve solo lo
  suyo (reglas en `security/alquiler_security.xml`) y el Panel muestra la empresa activa.

## Crear la base

```bash
bash extra-addons/alquileres/scripts/crear_alquileres.sh
```

Crea la base `alquileres` con las propiedades (Casa Caacupé, Casa Itauguá y Edificio Ypacaraí con 5
departamentos: 2 en el piso 1, 1 en el piso 2 y 2 en el piso 3) y datos de ejemplo con teléfonos inventados
(0981 000 0xx): inquilinos, contratos, pagos, gastos, reparaciones, un acta e interesados. Las fechas se calculan
desde el día en que se corre.

## Pruebas

```bash
bash scripts/pruebas.sh alquileres
```

Corren en la base `pruebas_alquileres` (el script la crea la primera vez), no en `alquileres`, para que los números
de contratos y recibos de la base real no queden salteados.
