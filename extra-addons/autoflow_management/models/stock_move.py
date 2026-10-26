# -*- coding: utf-8 -*-
from odoo import fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    autoflow_order_id = fields.Many2one('autoflow.workshop.order', string='Orden de servicio',
                                        readonly=True, index='btree_not_null')
