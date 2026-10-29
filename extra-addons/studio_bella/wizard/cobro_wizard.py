# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

from ..models.cobro import METODOS_PAGO


class BellaCobroWizard(models.TransientModel):
    """Caja: se elige cómo paga el cliente y, si paga en efectivo, se calcula el vuelto.

    Si la clienta tiene puntos, puede usar parte o todos como descuento.
    """
    _name = 'bella.cobro.wizard'
    _description = 'Cobrar'

    cita_id = fields.Many2one('bella.cita', string='Cita', readonly=True)
    venta_id = fields.Many2one('bella.venta', string='Venta', readonly=True)
    cliente_id = fields.Many2one('res.partner', string='Cliente', compute='_compute_documento')
    currency_id = fields.Many2one('res.currency', compute='_compute_documento')
    total = fields.Monetary('Total', compute='_compute_documento')
    metodo_pago = fields.Selection(METODOS_PAGO, string='Forma de pago', required=True, default='efectivo')
    diario_id = fields.Many2one('account.journal', string='Diario', compute='_compute_diario_id', store=True,
                                readonly=False, required=True, domain=[('type', 'in', ('cash', 'bank'))])

    # Puntos
    usa_puntos = fields.Boolean(compute='_compute_puntos')
    puntos_disponibles = fields.Integer('Puntos de la clienta', compute='_compute_puntos')
    puntos_maximos = fields.Integer('Se pueden usar hasta', compute='_compute_puntos')
    puntos_canje = fields.Integer('Puntos a usar')
    descuento_puntos = fields.Monetary('Descuento por puntos', compute='_compute_total_a_cobrar')
    total_a_cobrar = fields.Monetary('Total a cobrar', compute='_compute_total_a_cobrar')

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

    @api.depends('cita_id', 'venta_id', 'total')
    def _compute_puntos(self):
        for wizard in self:
            documento = wizard._documento()
            valor = documento.company_id.bella_puntos_valor if documento else 0
            wizard.usa_puntos = bool(documento) and documento._bella_suma_puntos()
            wizard.puntos_disponibles = (wizard.cliente_id._bella_saldo_puntos(documento.company_id)
                                         if wizard.usa_puntos else 0)
            # No más puntos de los que tiene ni de los que hacen falta para pagar todo.
            alcanzan = int(wizard.total // valor) if valor > 0 else 0
            wizard.puntos_maximos = min(wizard.puntos_disponibles, alcanzan)

    @api.depends('total', 'puntos_canje', 'cita_id', 'venta_id')
    def _compute_total_a_cobrar(self):
        for wizard in self:
            documento = wizard._documento()
            valor = documento.company_id.bella_puntos_valor if documento else 0
            wizard.descuento_puntos = max(wizard.puntos_canje, 0) * valor
            wizard.total_a_cobrar = wizard.total - wizard.descuento_puntos

    @api.depends('metodo_pago', 'monto_recibido', 'total_a_cobrar')
    def _compute_vuelto(self):
        for wizard in self:
            en_efectivo = wizard.metodo_pago == 'efectivo' and wizard.monto_recibido
            wizard.vuelto = max(wizard.monto_recibido - wizard.total_a_cobrar, 0) if en_efectivo else 0

    def action_cobrar(self):
        self.ensure_one()
        documento = self._documento()
        if not documento:
            raise UserError('No hay nada para cobrar.')
        if self.puntos_canje and not 0 < self.puntos_canje <= self.puntos_maximos:
            raise UserError(f'Se pueden usar hasta {self.puntos_maximos} puntos en este cobro.')
        if (self.metodo_pago == 'efectivo' and self.monto_recibido
                and self.currency_id.compare_amounts(self.monto_recibido, self.total_a_cobrar) < 0):
            raise UserError('El efectivo recibido es menor que el total a cobrar.')
        documento._bella_cobrar(self.metodo_pago, diario=self.diario_id, puntos=self.puntos_canje)
        return {'type': 'ir.actions.act_window_close'}
