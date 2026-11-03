# -*- coding: utf-8 -*-
from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _montos_en_dos_monedas(self):
        """El total en guaraníes y en dólares, con la cotización que se usó, para la factura y el recibo en PDF. Si
        la factura ya se pagó en parte, también lo que falta pagar. Salen de la línea del cliente (o del proveedor),
        así que son los mismos números que en la cuenta corriente. Vacío si el asiento no tiene esa línea."""
        self.ensure_one()
        lineas = self.line_ids.filtered(lambda l: l.account_type in ('asset_receivable', 'liability_payable'))
        if not lineas:
            return {}
        dolar = self.env.ref('base.USD')
        cotizacion = lineas[0].cotizacion
        valores = {
            'total_gs': abs(sum(lineas.mapped('balance'))),
            'total_usd': dolar.round(abs(sum(lineas.mapped('debe_usd')) - sum(lineas.mapped('haber_usd')))),
            'cotizacion': cotizacion,
            'fecha': lineas[0].date,
        }
        if self.is_invoice(include_receipts=True) and self.payment_state == 'partial' and cotizacion:
            falta = self.amount_residual  # en la moneda de la factura
            if self.currency_id == dolar:
                valores['saldo_usd'] = falta
                valores['saldo_gs'] = self.company_currency_id.round(falta * cotizacion)
            else:
                valores['saldo_gs'] = falta
                valores['saldo_usd'] = dolar.round(falta / cotizacion)
        return valores
