# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

from ..models.cobro import METODOS_PAGO


class BellaCobroWizard(models.TransientModel):
    """Caja: se elige cómo paga el cliente y, si paga en efectivo, se calcula el vuelto."""
    _name = 'bella.cobro.wizard'
    _description = 'Cobrar'

    cita_id = fields.Many2one('bella.cita', string='Cita', readonly=True)
    venta_id = fields.Many2one('bella.venta', string='Venta', readonly=True)
    cliente_id = fields.Many2one('res.partner', string='Cliente', compute='_compute_documento')
    currency_id = fields.Many2one('res.currency', compute='_compute_documento')
    total = fields.Monetary('Total a cobrar', compute='_compute_documento')
    metodo_pago = fields.Selection(METODOS_PAGO, string='Forma de pago', required=True, default='efectivo')
    diario_id = fields.Many2one('account.journal', string='Diario', compute='_compute_diario_id', store=True,
                                readonly=False, required=True, domain=[('type', 'in', ('cash', 'bank'))])
    monto_recibido = fields.Monetary('Efectivo recibido', help='Con cuánto paga el cliente, para calcular el vuelto.')
    vuelto = fields.Monetary('Vuelto', compute='_compute_vuelto')

    def _documento(self):
        self.ensure_one()
        return self.cita_id or self.venta_id

    @api.depends('cita_id', 'venta_id')
    def _compute_documento(self):
        for wizard in self:
            documento = wizard._documento()
            wizard.cliente_id = documento.cliente_id
            wizard.currency_id = documento.currency_id or self.env.company.currency_id
            wizard.total = documento.total

    @api.depends('metodo_pago', 'cita_id', 'venta_id')
    def _compute_diario_id(self):
        for wizard in self:
            documento = wizard._documento()
            wizard.diario_id = documento._bella_buscar_diario(wizard.metodo_pago) if documento else False

    @api.depends('metodo_pago', 'monto_recibido', 'total')
    def _compute_vuelto(self):
        for wizard in self:
            en_efectivo = wizard.metodo_pago == 'efectivo' and wizard.monto_recibido
            wizard.vuelto = max(wizard.monto_recibido - wizard.total, 0) if en_efectivo else 0

    def action_cobrar(self):
        self.ensure_one()
        documento = self._documento()
        if not documento:
            raise UserError('No hay nada para cobrar.')
        if (self.metodo_pago == 'efectivo' and self.monto_recibido
                and self.currency_id.compare_amounts(self.monto_recibido, self.total) < 0):
            raise UserError('El efectivo recibido es menor que el total a cobrar.')
        documento._bella_cobrar(self.metodo_pago, diario=self.diario_id)
        return {'type': 'ir.actions.act_window_close'}
