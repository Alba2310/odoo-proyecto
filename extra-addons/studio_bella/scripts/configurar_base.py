# -*- coding: utf-8 -*-
"""Deja lista una base de Studio Bella para Paraguay y carga los datos de ejemplo.

Se corre una sola vez, con la base creada en español (Paraguay) y el módulo instalado SIN los datos
de demostración de Odoo (así no aparecen los clientes y productos de ejemplo de Odoo):

    docker compose exec -T web odoo shell -d peluqueria --no-http < extra-addons/studio_bella/scripts/configurar_base.py

Hace esto:
* Empresa "Studio Bella" en Asunción, en guaraníes, con el ícono como logo y el horario de la peluquería.
* IVA 10 % y 5 % incluidos en el precio, como impuestos por defecto (el plan contable genérico
  de Odoo trae un impuesto de 15 % que acá se archiva).
* Carga demo/demo_data.xml (servicios, productos con stock, estilistas, clientes, citas y cobros)
  y demo/demo_compras.xml (proveedores, stock mínimo y pedidos a proveedores).
* Cierra la caja de los días de esos cobros.
"""
import base64

from odoo import fields
from odoo.tools import convert_file, file_open

admin = env.ref('base.user_admin')
env = env(user=admin.id, context=dict(env.context, lang='es_PY', tz='America/Asuncion'))
company = env.company
paraguay = env.ref('base.py')

with file_open('studio_bella/static/description/icon.png', 'rb') as icono:
    logo = base64.b64encode(icono.read())
company.write({
    'name': 'Studio Bella',
    'street': 'Av. España 1520',
    'city': 'Asunción',
    'country_id': paraguay.id,
    'phone': '021 600 123',
    'email': 'studiobella@example.com',
    'logo': logo,
    'account_fiscal_country_id': paraguay.id,
    'account_price_include': 'tax_included',
    'resource_calendar_id': env.ref('studio_bella.horario_studio_bella').id,
})
admin.write({'tz': 'America/Asuncion', 'lang': 'es_PY'})
# El depósito se creó con el nombre de la empresa de fábrica ("My Company: Recepciones").
env['stock.warehouse'].search([('company_id', '=', company.id)], limit=1).name = 'Studio Bella'
# La peluquería abre de lunes a sábado: la agenda empieza la semana el lunes.
env['res.lang']._lang_get('es_PY').week_start = '1'

# Al instalar Facturación, el plan contable genérico deja la moneda en dólares.
# Se puede cambiar mientras no haya asientos contables.
guaranies = env.ref('base.PYG')
if company.currency_id != guaranies:
    guaranies.active = True
    company.currency_id = guaranies

# IVA: se copian los impuestos del plan genérico para quedarse con sus cuentas contables.
Tax = env['account.tax'].with_context(active_test=False)
if not Tax.search([('company_id', '=', company.id), ('name', '=', 'IVA 10 %')]):
    for uso in ('sale', 'purchase'):
        modelo = Tax.search([('company_id', '=', company.id), ('type_tax_use', '=', uso), ('amount', '=', 15)],
                            limit=1)
        impuestos = {}
        for tasa in (10, 5):
            grupo = env['account.tax.group'].search([('company_id', '=', company.id), ('name', '=', f'IVA {tasa} %')],
                                                    limit=1)
            if not grupo:
                grupo = env['account.tax.group'].create({
                    'name': f'IVA {tasa} %', 'country_id': paraguay.id, 'company_id': company.id,
                })
            impuestos[tasa] = modelo.copy({
                'name': f'IVA {tasa} %',
                'description': f'IVA {tasa} %',
                'invoice_label': f'IVA {tasa} %',
                'amount': tasa,
                'price_include_override': 'tax_included',
                'tax_group_id': grupo.id,
                'country_id': paraguay.id,
            })
        campo = 'account_sale_tax_id' if uso == 'sale' else 'account_purchase_tax_id'
        company[campo] = impuestos[10]
    Tax.search([('company_id', '=', company.id), ('amount', '=', 15)]).active = False

# Datos de ejemplo de Studio Bella (las fechas de las citas se calculan desde hoy).
# Cada archivo se carga una sola vez: se reconoce por uno de sus registros.
for archivo, registro in (('demo/demo_data.xml', 'cita_01'), ('demo/demo_compras.xml', 'compra_01')):
    if not env.ref(f'studio_bella.{registro}', raise_if_not_found=False):
        convert_file(env, 'studio_bella', archivo, {}, mode='init', noupdate=True, kind='demo')

# Cierres de caja de los días con cobros de ejemplo: con 200.000 de cambio. El miércoles faltaron 10.000 y el
# sábado se sacaron 50.000 de la caja para compras chicas.
if not env['bella.cierre.caja'].search_count([]):
    facturas = env['bella.cita'].search([]).factura_id | env['bella.venta'].search([]).factura_id
    hoy = fields.Date.context_today(admin)
    # Solo días anteriores: la caja de hoy queda abierta para seguir cobrando.
    for dia in sorted(dia for dia in set(facturas.mapped('invoice_date')) if dia < hoy):
        cierre = env['bella.cierre.caja'].create({'fecha': dia, 'fondo_inicial': 200000})
        if dia.weekday() == 5:
            cierre.write({'retiros': 50000, 'nota': 'Compra de café, azúcar y agua para las clientas.'})
        cierre.efectivo_contado = cierre.efectivo_esperado - (10000 if dia.weekday() == 2 else 0)
        cierre.action_cerrar()

env.cr.commit()
print('Studio Bella: base configurada.')
print('Citas:', env['bella.cita'].search_count([]), '· Facturas:',
      env['account.move'].search_count([('move_type', '=', 'out_invoice')]),
      '· Pedidos a proveedores:', env['purchase.order'].search_count([]))
