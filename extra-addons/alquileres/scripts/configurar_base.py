# -*- coding: utf-8 -*-
"""Deja lista una base de Alquileres para Paraguay y carga las propiedades con datos de ejemplo.

Se corre una sola vez, con la base creada en español (Paraguay) y el módulo instalado:

    docker compose exec -T web odoo shell -d alquileres --no-http < extra-addons/alquileres/scripts/configurar_base.py

Hace esto:
* Empresa en guaraníes, con el ícono como logo. Al entrar, el administrador va directo al tablero de control.
* Las propiedades: Casa Caacupé, Casa Itauguá y Edificio Ypacaraí (5 departamentos: 2 en el piso 1, 1 en el
  piso 2 y 2 en el piso 3).
* Inquilinos y contratos de ejemplo, con sus pagos. Las fechas se calculan desde hoy, así siempre hay un poco de
  todo: inquilinos al día, uno que debe, uno que pagó una parte, uno que vence en 2 días, un contrato que termina
  pronto y un departamento libre. Los teléfonos son inventados (0981 000 0xx).
* Gastos de los últimos meses, pedidos de mantenimiento, reajustes, un acta de entrada e interesados de la página
  "Se alquila". Esta parte se carga aparte (si todavía no hay gastos), así también sirve en una base que ya tenía
  los contratos.
"""
import base64
from datetime import timedelta
from itertools import cycle

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tools import file_open

from odoo.addons.alquileres.models.contrato import vencimiento_del_mes

admin = env.ref('base.user_admin')
env = env(user=admin.id, context=dict(env.context, lang='es_PY', tz='America/Asuncion'))
company = env.company

with file_open('alquileres/static/description/icon.png', 'rb') as icono:
    logo = base64.b64encode(icono.read())
company.write({'name': 'Alquileres', 'country_id': env.ref('base.py').id, 'logo': logo})
guaranies = env.ref('base.PYG')
if company.currency_id != guaranies:
    guaranies.active = True
    company.currency_id = guaranies
admin.write({'tz': 'America/Asuncion', 'lang': 'es_PY',
             'action_id': env.ref('alquileres.action_alquiler_control').id})

if not env['alquiler.propiedad'].search_count([]):
    Propiedad = env['alquiler.propiedad']
    caacupe = Propiedad.create({'name': 'Casa Caacupé', 'tipo': 'casa', 'ciudad': 'Caacupé', 'sequence': 1})
    itaugua = Propiedad.create({'name': 'Casa Itauguá', 'tipo': 'casa', 'ciudad': 'Itauguá', 'sequence': 2})
    ypacarai = Propiedad.create({
        'name': 'Edificio Ypacaraí', 'tipo': 'edificio', 'ciudad': 'Ypacaraí', 'sequence': 3,
        'unidad_ids': [
            (0, 0, {'name': 'Depto 1', 'piso': 1, 'descripcion': '1 dormitorio', 'alquiler_sugerido': 1300000}),
            (0, 0, {'name': 'Depto 2', 'piso': 1, 'descripcion': '1 dormitorio', 'alquiler_sugerido': 1300000}),
            (0, 0, {'name': 'Depto 3', 'piso': 2, 'descripcion': '2 dormitorios, ocupa todo el piso',
                    'alquiler_sugerido': 1800000}),
            (0, 0, {'name': 'Depto 4', 'piso': 3, 'descripcion': '1 dormitorio', 'alquiler_sugerido': 1300000}),
            (0, 0, {'name': 'Depto 5', 'piso': 3, 'descripcion': '1 dormitorio', 'alquiler_sugerido': 1300000}),
        ],
    })
    caacupe.unidad_ids.alquiler_sugerido = 2000000
    itaugua.unidad_ids.alquiler_sugerido = 2300000
    deptos = {unidad.name: unidad for unidad in ypacarai.unidad_ids}

    hoy = fields.Date.context_today(admin)
    en_dos_dias = (hoy + timedelta(days=2)).day
    # unidad, inquilino, teléfono, alquiler, día de pago, meses desde que empezó, meses de contrato, medio de pago
    contratos = [
        (caacupe.unidad_ids, 'María González', '0981 000 001', 2000000, 10, 8, 24, 'transferencia'),
        (itaugua.unidad_ids, 'Carlos Benítez', '0981 000 002', 2300000, 1, 14, 24, 'efectivo'),
        (deptos['Depto 1'], 'Lucía Ramírez', '0981 000 003', 1300000, en_dos_dias, 5, 12, 'billetera'),
        (deptos['Depto 2'], 'Jorge Villalba', '0981 000 004', 1300000, 15, 3, 12, 'efectivo'),
        (deptos['Depto 4'], 'Ana Duarte', '0981 000 005', 1300000, 5, 11, 12, 'transferencia'),
        (deptos['Depto 5'], 'Ramón Acosta', '0981 000 006', 1300000, 20, 2, 12, 'transferencia'),
    ]
    garantes = {
        'Carlos Benítez': env['res.partner'].create({'name': 'Rosa Benítez', 'phone': '0981 000 012'}),
        'Jorge Villalba': env['res.partner'].create({'name': 'Pedro Villalba', 'phone': '0981 000 014'}),
    }
    dias_de_demora = cycle([0, 2, 1, 4, 0, 3, 1])
    for unidad, nombre, telefono, monto, dia_pago, meses, duracion, medio in contratos:
        inicio = vencimiento_del_mes(hoy.replace(day=1) - relativedelta(months=meses), dia_pago)
        contrato = env['alquiler.contrato'].create({
            'unidad_id': unidad.id,
            'inquilino_id': env['res.partner'].create({'name': nombre, 'phone': telefono}).id,
            'garante_id': garantes[nombre].id if nombre in garantes else False,
            'monto': monto,
            'deposito': monto,
            'dia_pago': dia_pago,
            'fecha_inicio': inicio,
            'fecha_fin': inicio + relativedelta(months=duracion, days=-1),
        })
        contrato.action_activar()
        vencidas = contrato.cuota_ids.filtered(lambda c: c.fecha_vencimiento < hoy).sorted('fecha_vencimiento')
        for cuota in vencidas:
            ultima = cuota == vencidas[-1]
            if ultima and nombre == 'Carlos Benítez':
                continue  # debe el último mes
            fecha = min(cuota.fecha_vencimiento + timedelta(days=next(dias_de_demora)), hoy)
            pagar = 800000 if ultima and nombre == 'Jorge Villalba' else cuota.monto  # pagó una parte
            env['alquiler.pago'].create({'cuota_id': cuota.id, 'fecha': fecha, 'monto': pagar, 'medio': medio})

# Gastos, reparaciones, cargos, actas, reajustes e interesados de ejemplo (se cargan una sola vez).
propiedades = {propiedad.name: propiedad for propiedad in env['alquiler.propiedad'].search([])}
if not env['alquiler.gasto'].search_count([]) and len(propiedades) >= 3 and 'Edificio Ypacaraí' in propiedades:
    hoy = fields.Date.context_today(admin)
    caacupe, itaugua = propiedades['Casa Caacupé'], propiedades['Casa Itauguá']
    ypacarai = propiedades['Edificio Ypacaraí']
    deptos = {unidad.name: unidad for unidad in ypacarai.unidad_ids}
    if not company.phone:
        company.phone = '0981 000 000'

    # Para la página "Se alquila"
    (caacupe.unidad_ids | itaugua.unidad_ids).write({'dormitorios': 3, 'banos': 2})
    ypacarai.unidad_ids.write({'dormitorios': 1, 'banos': 1})
    deptos['Depto 3'].write({
        'dormitorios': 2,
        'detalle_web': 'Ocupa todo el segundo piso: living comedor, cocina, balcón al frente y lavadero. '
                       'Recién pintado, a tres cuadras del lago.',
    })

    # Gastos de los últimos meses: luz y limpieza del edificio, impuesto inmobiliario y la pintura del Depto 3.
    Gasto = env['alquiler.gasto']
    for atras in range(6):
        mes = hoy.replace(day=1) - relativedelta(months=atras)
        for dia, nombre, categoria, monto, proveedor in (
                (9, 'Luz del pasillo y la bomba de agua', 'servicios', 180000, 'ANDE'),
                (14, 'Limpieza de escaleras y pasillos', 'limpieza', 250000, 'Doña Carmen')):
            fecha = mes.replace(day=dia)
            if fecha <= hoy:
                Gasto.create({'name': nombre, 'fecha': fecha, 'propiedad_id': ypacarai.id, 'categoria': categoria,
                              'monto': monto, 'proveedor': proveedor})
    pago_impuesto = hoy.replace(month=2, day=10)
    if pago_impuesto <= hoy:
        for propiedad, monto in ((caacupe, 420000), (itaugua, 510000), (ypacarai, 980000)):
            Gasto.create({'name': f'Impuesto inmobiliario {hoy.year}', 'fecha': pago_impuesto,
                          'propiedad_id': propiedad.id, 'categoria': 'impuesto', 'monto': monto,
                          'proveedor': f'Municipalidad de {propiedad.ciudad}'})
    Gasto.create({'name': 'Pintura completa del Depto 3', 'fecha': hoy - timedelta(days=15),
                  'propiedad_id': ypacarai.id, 'unidad_id': deptos['Depto 3'].id, 'categoria': 'reparacion',
                  'monto': 1200000, 'proveedor': 'Pintor Julio Cáceres'})

    # Pedidos de mantenimiento: uno resuelto (lo pagó el dueño), uno en proceso y uno urgente sin empezar.
    Pedido = env['alquiler.mantenimiento']
    Pedido.create({'name': 'Cambio de cerradura de la puerta principal', 'unidad_id': caacupe.unidad_ids.id,
                   'fecha': hoy - timedelta(days=12), 'responsable': 'Cerrajería Caacupé',
                   'costo': 250000}).action_resolver()
    Pedido.create({'name': 'No anda un enchufe del dormitorio', 'unidad_id': itaugua.unidad_ids.id,
                   'fecha': hoy - timedelta(days=4), 'responsable': 'Electricista Ramón Giménez',
                   'estado': 'en_proceso'})
    Pedido.create({'name': 'Pierde agua la canilla de la cocina', 'unidad_id': deptos['Depto 2'].id,
                   'fecha': hoy - timedelta(days=1), 'prioridad': '1'})

    # Contratos: cédulas, reajuste anual del 10 % y el agua del mes en la cuota de Lucía.
    cedulas = cycle(['3.456.789', '4.123.555', '5.890.112', '2.987.654', '4.765.321', '5.234.876'])
    for contrato in env['alquiler.contrato'].search([('estado', '=', 'vigente')]):
        contrato.inquilino_id.vat = next(cedulas)
        # El próximo reajuste se propone solo: el primer aniversario después de hoy (los que ya pasaron están en el
        # alquiler actual).
        contrato.reajuste_pct = 10
    lucia = env['alquiler.contrato'].search([('inquilino_id.name', '=', 'Lucía Ramírez')], limit=1)
    if lucia:
        env['alquiler.cuota.cargo'].create({'cuota_id': lucia._cuota_para_cargos().id, 'concepto': 'agua',
                                            'detalle': 'Agua del mes', 'monto': 85000})

    # Acta de entrada del último inquilino que entró.
    ultimo = env['alquiler.contrato'].search([('estado', '=', 'vigente')], order='fecha_inicio desc', limit=1)
    env['alquiler.acta'].create({'contrato_id': ultimo.id, 'tipo': 'entrada', 'fecha': ultimo.fecha_inicio,
                                 'lectura_ande': '018 452', 'lectura_agua': '00731', 'llaves': 2,
                                 'observaciones': 'Se entrega recién pintado. Una mancha chica en la pared del baño.'})

    # Interesados en el Depto 3, que está libre.
    Interesado = env['alquiler.interesado']
    Interesado.create({'name': 'Sofía Martínez', 'telefono': '0981 000 021', 'unidad_id': deptos['Depto 3'].id,
                       'mensaje': 'Somos una pareja con un bebé. ¿Se puede visitar el sábado?',
                       'desde_la_pagina': True})
    Interesado.create({'name': 'Diego Ortiz', 'telefono': '0981 000 022', 'unidad_id': deptos['Depto 3'].id,
                       'estado': 'contactado', 'desde_la_pagina': True})

admin.action_id = env.ref('alquileres.action_alquiler_panel').id  # al entrar, el Panel

env.cr.commit()
print('Alquileres: base configurada.')
print('Unidades:', env['alquiler.unidad'].search_count([]),
      '· Contratos vigentes:', env['alquiler.contrato'].search_count([('estado', '=', 'vigente')]),
      '· Cuotas:', env['alquiler.cuota'].search_count([]),
      '· Pagos:', env['alquiler.pago'].search_count([]))
