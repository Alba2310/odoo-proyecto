# -*- coding: utf-8 -*-
"""Deja lista una base de Cuenta corriente para Paraguay y carga clientes con movimientos en guaraníes y dólares.

Se corre una sola vez, con la base creada en español (Paraguay) y el módulo instalado SIN los datos de
demostración de Odoo:

    docker compose exec -T web odoo shell -d cuenta_corriente --no-http < extra-addons/cuenta_corriente/scripts/configurar_base.py

Hace esto:
* Empresa "Importadora Guaraní S.A." en Asunción, en guaraníes.
* IVA 10 % y 5 % incluidos en el precio, como impuestos por defecto (el plan contable genérico de Odoo trae uno
  de 15 % que acá se archiva).
* El dólar, con la cotización de hoy del BCP y las de los últimos dos meses inventadas alrededor de ella (los
  domingos rige la del sábado), y un banco en dólares. Desde mañana la del BCP se carga sola cada día.
* Datos de ejemplo, con fechas relativas a hoy: cinco clientes con facturas en dólares y en guaraníes, una nota de
  crédito, pagos completos y parciales en las dos monedas, una factura en dólares pagada con guaraníes y un anticipo.
  Se cargan una sola vez: si ya hay facturas, no se repiten.
"""
import base64
from datetime import timedelta

from odoo import Command, fields
from odoo.tools import file_open

admin = env.ref('base.user_admin')
env = env(user=admin.id, context=dict(env.context, lang='es_PY', tz='America/Asuncion'))
company = env.company
paraguay = env.ref('base.py')

with file_open('cuenta_corriente/static/description/icon.png', 'rb') as icono:
    logo = base64.b64encode(icono.read())
company.write({
    'name': 'Importadora Guaraní S.A.',
    'street': 'Av. España 1234',
    'city': 'Asunción',
    'country_id': paraguay.id,
    'phone': '021 600 700',
    'email': 'administracion@importadora.example.com',
    'vat': '80012345-6',
    'logo': logo,
    'account_fiscal_country_id': paraguay.id,
    'account_price_include': 'tax_included',
    # Con el diseño elegido, Odoo no pide configurarlo la primera vez que se imprime.
    'external_report_layout_id': env.ref('web.external_layout_standard').id,
})
# La página de inicio del administrador son los clientes con su saldo.
admin.write({'tz': 'America/Asuncion', 'lang': 'es_PY', 'action_id': env.ref('cuenta_corriente.action_clientes').id})
env['res.lang']._lang_get('es_PY').week_start = '1'
# En las facturas y los extractos: "RUC" en vez de "Tax ID" o "Número de identificación fiscal".
paraguay.vat_label = 'RUC'

# Al instalar Facturación, el plan contable genérico deja la moneda en dólares.
# Se puede cambiar mientras no haya asientos contables.
guaranies = env.ref('base.PYG')
if company.currency_id != guaranies:
    guaranies.active = True
    company.currency_id = guaranies
dolar = env.ref('base.USD')
dolar.active = True

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

IVA_10 = Tax.search([('company_id', '=', company.id), ('name', '=', 'IVA 10 %'), ('type_tax_use', '=', 'sale')],
                    limit=1)
IVA_10_COMPRAS = Tax.search([('company_id', '=', company.id), ('name', '=', 'IVA 10 %'),
                             ('type_tax_use', '=', 'purchase')], limit=1)

hoy = fields.Date.context_today(admin)

# Cotizaciones del dólar: una por día, menos los domingos. La de hoy es la referencial del BCP; las anteriores se
# inventan alrededor de ella (sin internet, alrededor de 7.370). Después se cargan solas todos los días.
if not env['res.currency.rate'].search_count([('currency_id', '=', dolar.id), ('company_id', '=', company.id)]):
    try:
        actual, origen_hoy = env['res.currency.rate']._cotizacion_bcp(), 'bcp'
    except Exception:
        actual, origen_hoy = 7370, 'manual'
    for dias in range(60, -1, -1):
        dia = hoy - timedelta(days=dias)
        if dia.weekday() == 6 and dias:
            continue
        cotizacion = round(actual - dias * 1.5 + (0, 10, -5, 15, 5, -10)[dias % 6], 2)
        env['res.currency.rate'].create({
            'name': dia, 'rate': 1 / cotizacion, 'currency_id': dolar.id, 'company_id': company.id,
            'origen': origen_hoy if not dias else 'manual',
        })

Journal = env['account.journal']
banco_usd = Journal.search([('company_id', '=', company.id), ('type', '=', 'bank'), ('currency_id', '=', dolar.id)],
                           limit=1)
if not banco_usd:
    banco_usd = Journal.create({'name': 'Banco en dólares', 'type': 'bank', 'code': 'BUSD', 'currency_id': dolar.id})
banco_gs = Journal.search([('company_id', '=', company.id), ('type', '=', 'bank'), ('currency_id', '=', False)],
                          limit=1)
caja = Journal.search([('company_id', '=', company.id), ('type', '=', 'cash')], limit=1)
# La forma de pago de los diarios que crea el plan contable al instalarse queda en inglés.
env['account.payment.method.line'].search([('name', '=', 'Manual Payment')]).name = 'Pago manual'

if env['account.move'].search_count([('move_type', '=', 'out_invoice')]):
    env.cr.commit()
    print('Cuenta corriente: la base ya tenía facturas; no se cargaron datos de ejemplo.')
else:
    def producto(nombre, precio, tipo='consu'):
        return env['product.product'].create({
            'name': nombre,
            'list_price': precio,
            'type': tipo,
            'taxes_id': [Command.set(IVA_10.ids)],
            'supplier_taxes_id': [Command.set(IVA_10_COMPRAS.ids)],
        })

    generador = producto('Generador 5 kVA', 6_200_000)
    bomba = producto('Bomba de agua 1 HP', 1_350_000)
    taladro = producto('Taladro percutor', 720_000)
    instalacion = producto('Instalación y puesta en marcha', 1_100_000, 'service')
    mantenimiento = producto('Mantenimiento', 250_000, 'service')

    a_30_dias = env.ref('account.account_payment_term_30days')

    def cliente(nombre, ruc, ciudad, celular, empresa=False, plazo=False):
        return env['res.partner'].create({
            'name': nombre, 'vat': ruc, 'city': ciudad, 'country_id': paraguay.id, 'mobile': celular,
            'is_company': empresa, 'property_payment_term_id': plazo and plazo.id,
        })

    ferreteria = cliente('Ferretería San José S.A.', '80023456-1', 'Luque', '0981 123 456', True, a_30_dias)
    constructora = cliente('Constructora Ñandutí S.A.', '80034567-3', 'San Lorenzo', '0982 234 567', True,
                           a_30_dias)
    lucia = cliente('Lucía Benítez', '4567890-2', 'Asunción', '0971 345 678')
    pedro = cliente('Pedro Giménez', '3456789-4', 'Fernando de la Mora', '0985 456 789')
    farmacia = cliente('Farmacia Central', '80045678-5', 'Asunción', '0991 567 890', True)

    def factura(socio, dias, lineas, moneda, tipo='out_invoice'):
        """Las líneas son (producto, cantidad, precio con IVA en la moneda de la factura)."""
        documento = env['account.move'].create({
            'move_type': tipo,
            'partner_id': socio.id,
            'invoice_date': hoy - timedelta(days=dias),
            'currency_id': moneda.id,
            'invoice_line_ids': [Command.create({'product_id': p.id, 'quantity': cantidad, 'price_unit': precio})
                                 for p, cantidad, precio in lineas],
        })
        documento.action_post()
        return documento

    def cobro(documento, dias, moneda, diario, monto=None):
        """Sin monto se cobra todo lo que falta, pasado a la moneda del cobro con la cotización de ese día."""
        valores = {'payment_date': hoy - timedelta(days=dias), 'currency_id': moneda.id, 'journal_id': diario.id}
        if monto:
            valores['amount'] = monto
        env['account.payment.register'].with_context(
            active_model='account.move', active_ids=documento.ids,
        ).create(valores)._create_payments()

    def conciliar(*documentos):
        lineas = sum((d.line_ids for d in documentos), env['account.move.line'])
        lineas.filtered(lambda l: l.account_type == 'asset_receivable' and not l.reconciled).reconcile()

    # En orden de fecha, como se hubieran cargado.
    f_ferreteria_1 = factura(ferreteria, 55, [(generador, 4, 850)], dolar)
    f_constructora_1 = factura(constructora, 45, [(generador, 2, 850), (instalacion, 1, 150)], dolar)
    cobro(f_ferreteria_1, 40, dolar, banco_usd)
    f_lucia = factura(lucia, 35, [(taladro, 1, 720_000), (mantenimiento, 1, 250_000)], guaranies)
    cobro(f_lucia, 33, guaranies, caja, 500_000)
    cobro(f_constructora_1, 30, guaranies, banco_gs)  # debía en dólares y pagó con guaraníes
    factura(pedro, 25, [(bomba, 1, 1_350_000)], guaranies)
    f_ferreteria_2 = factura(ferreteria, 20, [(taladro, 10, 95), (bomba, 2, 180)], dolar)
    cobro(f_lucia, 15, guaranies, caja)
    devolucion = factura(ferreteria, 12, [(taladro, 1, 95)], dolar, 'out_refund')
    conciliar(f_ferreteria_2, devolucion)
    f_pedro = factura(pedro, 10, [(generador, 1, 850)], dolar)
    factura(constructora, 8, [(bomba, 3, 180)], dolar)
    anticipo = env['account.payment'].create({
        'payment_type': 'inbound',
        'partner_type': 'customer',
        'partner_id': farmacia.id,
        'amount': 1000,
        'currency_id': dolar.id,
        'journal_id': banco_usd.id,
        'date': hoy - timedelta(days=6),
        'memo': 'Anticipo',
    })
    anticipo.action_post()
    cobro(f_ferreteria_2, 5, dolar, banco_usd, 600)
    cobro(f_pedro, 3, dolar, banco_usd, 300)
    f_farmacia = factura(farmacia, 2, [(generador, 2, 850)], dolar)
    conciliar(f_farmacia, anticipo.move_id)

    env.cr.commit()
    print('Cuenta corriente: base configurada con los datos de ejemplo.')
    for socio in (ferreteria, constructora, lucia, pedro, farmacia):
        print(f'  {socio.name}: saldo {socio.saldo_gs:,.0f} Gs · {socio.saldo_usd:,.2f} USD')
