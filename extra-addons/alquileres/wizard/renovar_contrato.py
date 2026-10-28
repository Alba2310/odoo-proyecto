# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..models.utiles import fecha_larga, guaranies


class AlquilerRenovarWizard(models.TransientModel):
    """Renovar un contrato: hasta cuándo sigue y con qué alquiler. Las cuotas siguen saliendo del mismo contrato."""
    _name = 'alquiler.renovar.wizard'
    _description = 'Renovar contrato'

    contrato_id = fields.Many2one('alquiler.contrato', string='Contrato', required=True, readonly=True)
    currency_id = fields.Many2one(related='contrato_id.currency_id')
    fecha_fin_actual = fields.Date(related='contrato_id.fecha_fin', string='Vence el')
    fecha_fin = fields.Date('Nueva fecha de fin', compute='_compute_propuesta', store=True, readonly=False,
                            precompute=True, required=True)
    monto = fields.Monetary('Alquiler mensual', compute='_compute_propuesta', store=True, readonly=False,
                            precompute=True, required=True)

    @api.depends('contrato_id')
    def _compute_propuesta(self):
        # Se propone otro año con el alquiler reajustado (si el contrato tiene reajuste).
        for asistente in self:
            contrato = asistente.contrato_id
            base = contrato.fecha_fin or fields.Date.context_today(self)
            asistente.fecha_fin = base + relativedelta(years=1)
            asistente.monto = contrato.monto_reajustado if contrato.reajuste_pct else contrato.monto

    def action_confirmar(self):
        self.ensure_one()
        contrato = self.contrato_id
        if contrato.estado != 'vigente':
            raise UserError('Solo se puede renovar un contrato vigente.')
        if contrato.fecha_fin and self.fecha_fin <= contrato.fecha_fin:
            raise UserError('La nueva fecha de fin tiene que ser después de la actual.')
        valores = {'fecha_fin': self.fecha_fin, 'monto': self.monto}
        if contrato.reajuste_pct and self.monto != contrato.monto:
            # El alquiler nuevo ya trae el aumento: el próximo reajuste es al año de empezar la renovación.
            inicio = (contrato.fecha_fin or fields.Date.context_today(self)) + relativedelta(days=1)
            valores['fecha_reajuste'] = inicio + relativedelta(years=1)
        contrato.write(valores)
        contrato.message_post(body=f'Contrato renovado hasta el {fecha_larga(self.fecha_fin)}, con un alquiler de '
                                   f'{guaranies(self.monto)} por mes.')
        return {'type': 'ir.actions.act_window_close'}
