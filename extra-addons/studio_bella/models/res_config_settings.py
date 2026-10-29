# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    bella_url_turnos = fields.Char(related='company_id.bella_url_turnos', readonly=False)
    bella_puntos_activo = fields.Boolean(related='company_id.bella_puntos_activo', readonly=False)
    bella_puntos_monto = fields.Monetary(related='company_id.bella_puntos_monto', readonly=False)
    bella_puntos_valor = fields.Monetary(related='company_id.bella_puntos_valor', readonly=False)
