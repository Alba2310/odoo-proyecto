# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import api, fields, models

# Los movimientos de la cuenta corriente: lo confirmado en las cuentas a cobrar de los clientes.
DOMINIO_CUENTA_CORRIENTE = [('parent_state', '=', 'posted'), ('account_type', '=', 'asset_receivable')]

TIPOS_MOVIMIENTO = [
    ('factura', 'Factura'),
    ('cobro', 'Cobro'),
    ('nota_credito', 'Nota de crédito'),
    ('devolucion', 'Devolución de dinero'),
    ('ajuste', 'Ajuste por cotización'),
    ('otro', 'Otro'),
]


class AccountMoveLine(models.Model):
    """El Debe Gs y el Haber Gs son el Debe y el Haber de la contabilidad (Odoo lleva todo en la moneda de la
    empresa); acá se agregan el Debe y el Haber en dólares, la cotización con que se pasó de una moneda a la otra,
    y lo que hace falta para leer la cuenta corriente sin saber contabilidad: tipo, detalle y saldo."""
    _inherit = 'account.move.line'

    moneda_usd_id = fields.Many2one('res.currency', compute='_compute_moneda_usd_id')
    cotizacion = fields.Float(
        'Cotización', digits=(16, 2), aggregator=None, compute='_compute_columnas_usd', store=True,
        help='Guaraníes por cada dólar el día del movimiento.')
    debe_usd = fields.Monetary(
        'Debe USD', currency_field='moneda_usd_id', compute='_compute_columnas_usd', store=True)
    haber_usd = fields.Monetary(
        'Haber USD', currency_field='moneda_usd_id', compute='_compute_columnas_usd', store=True)
    tipo_movimiento = fields.Selection(TIPOS_MOVIMIENTO, 'Tipo', compute='_compute_descripcion')
    detalle = fields.Char('Detalle', compute='_compute_descripcion')
    moneda_texto = fields.Char('Moneda', compute='_compute_descripcion')
    saldo_gs = fields.Monetary('Saldo Gs', currency_field='company_currency_id', compute='_compute_saldos')
    saldo_usd = fields.Monetary('Saldo USD', currency_field='moneda_usd_id', compute='_compute_saldos')

    def _compute_moneda_usd_id(self):
        self.moneda_usd_id = self.env.ref('base.USD')

    def _es_diferencia_de_cambio(self):
        self.ensure_one()
        return self.journal_id == self.company_id.currency_exchange_journal_id

    @api.depends('balance', 'amount_currency', 'currency_id', 'date', 'journal_id', 'parent_state')
    def _compute_columnas_usd(self):
        """Lo que se hizo en dólares queda con su monto en dólares, y en guaraníes con la cotización que usó la
        contabilidad ese día. Lo que se hizo en guaraníes pasa a dólares con la cotización del día del movimiento;
        como hace Odoo con las facturas en dólares, queda fija al confirmar aunque después se corrija la cotización.

        Las diferencias de cambio que arma Odoo al conciliar un cobro con una deuda en dólares van solo en
        guaraníes (Odoo las asienta en el diario de diferencias de cambio de la empresa): hacen que, cuando el
        cliente cancela lo que debía en dólares, el saldo en guaraníes también quede en cero."""
        dolar = self.env.ref('base.USD')
        cotizaciones = {}
        for linea in self:
            if linea._es_diferencia_de_cambio() or not linea.amount_currency:
                monto_usd = cotizacion = 0.0
            elif linea.currency_id == dolar:
                monto_usd = linea.amount_currency
                cotizacion = abs(linea.balance / linea.amount_currency)
            else:
                clave = (linea.company_id, linea.date)
                if clave not in cotizaciones:
                    cotizaciones[clave] = dolar._get_conversion_rate(
                        dolar, linea.company_currency_id, linea.company_id, linea.date or fields.Date.today())
                cotizacion = cotizaciones[clave]
                monto_usd = dolar.round(linea.balance / cotizacion)
            linea.cotizacion = cotizacion
            linea.debe_usd = max(monto_usd, 0.0)
            linea.haber_usd = max(-monto_usd, 0.0)

    @api.depends('move_id.move_type', 'move_id.origin_payment_id', 'move_id.statement_line_id', 'journal_id',
                 'currency_id')
    def _compute_descripcion(self):
        """Qué fue cada movimiento, en palabras: "Cobro de la factura INV/2026/00001 · Banco en dólares"."""
        dolar = self.env.ref('base.USD')
        for linea in self:
            asiento = linea.move_id
            pago = asiento.origin_payment_id
            if linea._es_diferencia_de_cambio():
                tipo, detalle = 'ajuste', 'Ajuste por cambio de cotización del dólar'
            elif asiento.move_type == 'out_invoice':
                tipo, detalle = 'factura', f'Factura {asiento.name}'
            elif asiento.move_type == 'out_refund':
                tipo, detalle = 'nota_credito', f'Nota de crédito {asiento.name}'
                if asiento.reversed_entry_id:
                    detalle += f' (de la factura {asiento.reversed_entry_id.name})'
            elif pago.payment_type == 'outbound':
                tipo, detalle = 'devolucion', f'Devolución de dinero · {asiento.journal_id.name}'
            elif pago or asiento.statement_line_id:
                tipo = 'cobro'
                facturas = pago.reconciled_invoice_ids.filtered(lambda f: f.move_type == 'out_invoice')
                if facturas:
                    detalle = ('Cobro de la factura ' if len(facturas) == 1 else 'Cobro de las facturas ') + \
                        ', '.join(facturas.mapped('name'))
                else:
                    detalle = f'Cobro a cuenta: {pago.memo}' if pago.memo else 'Cobro a cuenta'
                detalle += f' · {asiento.journal_id.name}'
            else:
                tipo, detalle = 'otro', linea.name or asiento.name
            linea.tipo_movimiento = tipo
            linea.detalle = detalle
            if tipo == 'ajuste' or linea.currency_id == linea.company_currency_id:
                linea.moneda_texto = 'Guaraníes'
            elif linea.currency_id == dolar:
                linea.moneda_texto = 'Dólares'
            else:
                linea.moneda_texto = linea.currency_id.name

    def _compute_saldos(self):
        """Lo que debía el cliente después de cada movimiento: se cuenta toda su cuenta corriente en orden de fecha,
        aunque la lista esté filtrada o se vea un solo mes."""
        clientes = self.filtered('id').partner_id.commercial_partner_id
        saldos = {}
        if clientes:
            acumulado = defaultdict(lambda: [0.0, 0.0])
            movimientos = self.search(
                [('partner_id', 'child_of', clientes.ids), *DOMINIO_CUENTA_CORRIENTE], order='date, id')
            for movimiento in movimientos:
                saldo = acumulado[movimiento.company_id, movimiento.partner_id.commercial_partner_id]
                saldo[0] += movimiento.balance
                saldo[1] += movimiento.debe_usd - movimiento.haber_usd
                saldos[movimiento.id] = (saldo[0], round(saldo[1], 2))
        for linea in self:
            linea.saldo_gs, linea.saldo_usd = saldos.get(linea.id, (0.0, 0.0))
