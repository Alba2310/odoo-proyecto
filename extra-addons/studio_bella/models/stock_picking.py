# -*- coding: utf-8 -*-
from odoo import models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _action_done(self):
        res = super()._action_done()
        # Al recibir mercadería se cierra el aviso de reponer; si una salida deja poco stock, se avisa.
        self.env['product.template']._bella_avisar_reposicion(self.move_ids.product_id.product_tmpl_id)
        return res
