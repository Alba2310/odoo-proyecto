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
        # Se propone otro año con el alquiler que corresponde el día que empieza la renovación: reajustado si el
        # reajuste llega hasta ese día; si el cron ya lo aplicó (contrato vencido que siguió vigente), el de ahora,
        # sin sumarle otro reajuste encima.
        for asistente in self:
            contrato = asistente.contrato_id
            if not contrato:
                asistente.fecha_fin = asistente.monto = False
                continue
            inicio = contrato._inicio_renovacion()
            asistente.fecha_fin = inicio - relativedelta(days=1) + relativedelta(years=1)
            asistente.monto = contrato._monto_para(inicio)

    def action_confirmar(self):
        self.ensure_one()
        contrato = self.contrato_id
        if contrato.estado != 'vigente':
            raise UserError('Solo se puede renovar un contrato vigente.')
        inicio = contrato._inicio_renovacion()
        if self.fecha_fin < inicio:
            raise UserError('La nueva fecha de fin tiene que ser después de la actual.')
        anterior = contrato.fecha_fin
        valores = {'fecha_fin': self.fecha_fin, 'monto_renovacion': 0, 'fecha_renovacion': False}
        if contrato.fecha_salida:
            # Se iba a ir, pero se queda: se anula la salida programada.
            valores.update(fecha_salida=False, deposito_descuento=0, deposito_motivo=False)
        if self.monto != contrato.monto:
            if inicio <= fields.Date.context_today(self):
                valores['monto'] = self.monto
            else:
                # Las cuotas que faltan del plazo actual siguen con el alquiler de ahora; el cron pasa al nuevo el
                # día que empieza la renovación.
                valores.update(monto_renovacion=self.monto, fecha_renovacion=inicio)
        if contrato.reajuste_pct and (self.monto != contrato.monto or not contrato.fecha_reajuste
                                      or contrato.fecha_reajuste <= inicio):
            # El alquiler de la renovación ya trae el aumento: el próximo reajuste es al año de empezar la renovación.
            valores['fecha_reajuste'] = inicio + relativedelta(years=1)
        contrato.write(valores)
        # Si el contrato terminaba a mitad de un mes de pago, esa cuota pasa a cobrar también los días de la
        # renovación (con su alquiler), sin cobrar dos veces los mismos días.
        contrato._ajustar_cuota_del_fin(anterior)
        desde = f' desde el {fecha_larga(inicio)}' if valores.get('fecha_renovacion') else ''
        contrato.message_post(body=f'Contrato renovado hasta el {fecha_larga(self.fecha_fin)}, con un alquiler de '
                                   f'{guaranies(self.monto)} por mes{desde}.')
        return {'type': 'ir.actions.act_window_close'}
