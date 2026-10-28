# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class AlquilerTerminarWizard(models.TransientModel):
    """Terminar un contrato: el día que se va el inquilino y la liquidación del depósito de garantía."""
    _name = 'alquiler.terminar.wizard'
    _description = 'Terminar contrato y liquidar el depósito'

    contrato_id = fields.Many2one('alquiler.contrato', string='Contrato', required=True, readonly=True)
    currency_id = fields.Many2one(related='contrato_id.currency_id')
    fecha = fields.Date('Se va el', required=True, default=fields.Date.context_today)
    deposito = fields.Monetary(related='contrato_id.deposito', string='Depósito de garantía')
    deuda = fields.Monetary('Queda debiendo', compute='_compute_liquidacion',
                            help='Cuotas sin pagar que vencen hasta ese día. Se pagan con el depósito.')
    descuento = fields.Monetary('Descuento por daños', help='Arreglos que no son por el uso normal (ver el acta de salida).')
    motivo = fields.Char('Motivo del descuento')
    a_devolver = fields.Monetary('A devolver', compute='_compute_liquidacion')

    @api.depends('contrato_id', 'fecha', 'descuento')
    def _compute_liquidacion(self):
        for asistente in self:
            pendientes = asistente.contrato_id.cuota_ids.filtered(
                lambda c: c.estado != 'pagada' and (not asistente.fecha or c.fecha_vencimiento <= asistente.fecha))
            asistente.deuda = sum(pendientes.mapped('saldo'))
            asistente.a_devolver = max(asistente.deposito - asistente.deuda - (asistente.descuento or 0), 0)

    def action_confirmar(self):
        self.ensure_one()
        if self.descuento < 0:
            raise UserError('El descuento no puede ser negativo.')
        if self.descuento and not self.motivo:
            raise UserError('Escriba el motivo del descuento: queda en el contrato.')
        self.contrato_id._terminar(self.fecha, self.descuento, self.motivo)
        return {'type': 'ir.actions.act_window_close'}
