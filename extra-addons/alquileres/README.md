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
   la cuota y se cobran junto con el alquiler.
6. **Cobros y gastos › Gastos**: lo que gasta el dueño en cada propiedad. **Reportes › Ganancia por propiedad**.
7. **Mantenimiento**: pedidos de reparación. Al resolverlos, el costo va a los gastos o a la cuota del inquilino.
8. **Contratos › Actas de entrega**: estado de la unidad al entrar y al salir, con fotos, medidores y llaves.
9. **Terminar contrato**: el depósito paga lo que quedó debiendo, se descuentan los daños y queda lo que hay que
   devolver. **Renovar** extiende el contrato con el alquiler nuevo.
10. **Se alquila › Interesados**: los que dejaron sus datos en la página pública. **Ver la página** la abre.

## Cómo funciona

- `models/contrato.py`: `_generar_cuotas` crea una cuota por mes hasta las que vencen en los próximos 10 días; el
  cron de las 6:00 primero aplica los reajustes que llegaron (`_aplicar_reajustes`) y después crea las cuotas. Las
  cuotas que vencen desde la fecha de reajuste ya salen con el monto nuevo. `_terminar` usa el depósito para pagar
  las cuotas pendientes (pagos con medio "Del depósito de garantía") y guarda el descuento por daños. Las
  cláusulas del contrato impreso salen de `_clausulas()`.
- `models/cuota.py`: total = alquiler + cargos extra; estado (pendiente, pago parcial, pagada) según los pagos.
  Avisos: `proximo_aviso` arranca 3 días antes de vencer y después de cada aviso pasa al día del vencimiento o a 3
  días después. `calificar()` da el puntaje de cómo paga el inquilino (a tiempo = hasta 3 días después de vencer).
- WhatsApp: abre `wa.me` con el texto (gratis, sin la API de WhatsApp Business), igual que Studio Bella.
- `models/resultado.py`: vista SQL con lo cobrado (sin los pagos con el depósito) y los gastos, para la ganancia.
- `models/panel.py` + `static/src/panel/`: los datos y la pantalla del Panel (acción de cliente en OWL).
- `controllers/se_alquila.py` + `views/se_alquila_templates.xml` + `static/se_alquila/`: la página pública. Como
  toda ruta pública, necesita un Odoo con una sola base: el servicio `oga` de docker-compose (puerto 8072,
  `--db-filter=^alquileres$`), en http://se-alquila.localhost:8072/se-alquila. El botón "Consultar" escribe al
  teléfono de la empresa (Ajustes); la dirección que abre "Ver la página" está en el parámetro
  `alquileres.url_pagina`.
- Grupos: **Encargado de cobros** (registra pagos, cargos y avisos, carga reparaciones y actas) y
  **Administrador** (además propiedades, contratos, gastos y reportes).

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
docker compose exec -T web odoo -c /etc/odoo/odoo.conf -d alquileres -u alquileres --test-enable --test-tags /alquileres --stop-after-init --http-port=8079
```
