# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ReporteExtracto(models.AbstractModel):
    """Datos del extracto en PDF. Desde el asistente, el cliente y el período llegan en `data` (la pantalla no
    manda los ids en la dirección del PDF cuando hay data); si se imprime desde el menú Imprimir del cliente, llegan
    los ids y sale toda su cuenta corriente hasta hoy."""
    _name = 'report.cuenta_corriente.reporte_extracto'
    _description = 'Extracto de cuenta corriente'

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        desde = fields.Date.to_date(data.get('fecha_desde'))
        hasta = fields.Date.to_date(data.get('fecha_hasta')) or fields.Date.context_today(self)
        clientes = self.env['res.partner'].browse(docids or data.get('cliente_ids')).commercial_partner_id
        return {
            'docs': clientes,
            'extractos': {cliente.id: cliente._extracto_cuenta_corriente(desde, hasta) for cliente in clientes},
            'desde': desde,
            'hasta': hasta,
            'moneda_gs': self.env.company.currency_id,
            'moneda_usd': self.env.ref('base.USD'),
        }
