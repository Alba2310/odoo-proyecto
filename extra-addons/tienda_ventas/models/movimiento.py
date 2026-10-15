# -*- coding: utf-8 -*-
from odoo import fields, models


class TiendaMovimiento(models.Model):
    _inherit = 'tienda.movimiento'

    tipo = fields.Selection(selection_add=[
        ('venta', 'Venta'),
        ('anulacion', 'Anulación de venta'),
    ], ondelete={'venta': 'set default', 'anulacion': 'set default'})
    venta_id = fields.Many2one('tienda.venta', string='Venta', ondelete='set null',
                               readonly=True, index=True)
