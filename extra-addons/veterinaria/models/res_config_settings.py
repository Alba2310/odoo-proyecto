# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    vet_url_reserva = fields.Char(related='company_id.vet_url_reserva', readonly=False)
    vet_dias_aviso_vacuna = fields.Integer(related='company_id.vet_dias_aviso_vacuna', readonly=False)
    vet_horas_control = fields.Integer(related='company_id.vet_horas_control', readonly=False)
    vet_producto_internacion_id = fields.Many2one(related='company_id.vet_producto_internacion_id', readonly=False)
    vet_producto_hotel_id = fields.Many2one(related='company_id.vet_producto_hotel_id', readonly=False)
    vet_diario_efectivo_id = fields.Many2one(related='company_id.vet_diario_efectivo_id', readonly=False)
    vet_diario_tarjeta_id = fields.Many2one(related='company_id.vet_diario_tarjeta_id', readonly=False)
    vet_diario_transferencia_id = fields.Many2one(related='company_id.vet_diario_transferencia_id', readonly=False)
