# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_date, formatLang

from ..models.account_move_line import DOMINIO_CUENTA_CORRIENTE


class ExtractoCuenta(models.TransientModel):
    """Pide el cliente y el período, y descarga el extracto de su cuenta corriente en PDF."""
    _name = 'cuenta.corriente.extracto'
    _description = 'Extracto de cuenta corriente'

    partner_id = fields.Many2one('res.partner', 'Cliente', required=True)
    fecha_desde = fields.Date(
        'Desde', compute='_compute_fecha_desde', store=True, readonly=False,
        help='Se carga con la fecha del primer movimiento del cliente; se puede cambiar. '
             'Vacío: desde el primer movimiento.')
    fecha_hasta = fields.Date('Hasta', required=True, default=fields.Date.context_today)

    @api.depends('partner_id')
    def _compute_fecha_desde(self):
        for asistente in self:
            primero = self.env['account.move.line'].search([
                ('partner_id', 'child_of', asistente.partner_id.commercial_partner_id.ids),
                *DOMINIO_CUENTA_CORRIENTE,
            ], order='date, id', limit=1) if asistente.partner_id else False
            asistente.fecha_desde = primero and primero.date

    def action_descargar_pdf(self):
        self.ensure_one()
        if self.fecha_desde and self.fecha_desde > self.fecha_hasta:
            raise UserError('La fecha "Desde" tiene que ser anterior a la fecha "Hasta".')
        cliente = self.partner_id.commercial_partner_id
        extracto = cliente._extracto_cuenta_corriente(self.fecha_desde, self.fecha_hasta)
        if not extracto['movimientos']:
            raise UserError(self._aviso_sin_movimientos(cliente, extracto))
        # El cliente va también en data: cuando el reporte trae data, la pantalla pide el PDF sin los ids.
        return self.env.ref('cuenta_corriente.action_report_extracto').report_action(
            cliente, data={
                'cliente_ids': cliente.ids,
                'fecha_desde': fields.Date.to_string(self.fecha_desde),
                'fecha_hasta': fields.Date.to_string(self.fecha_hasta),
            })

    def _aviso_sin_movimientos(self, cliente, extracto):
        """En vez de bajar un extracto vacío: qué período se pidió y, si debía algo de antes, cuánto."""
        hasta = format_date(self.env, self.fecha_hasta)
        if self.fecha_desde:
            periodo = f'entre el {format_date(self.env, self.fecha_desde)} y el {hasta}'
        else:
            periodo = f'hasta el {hasta}'
        aviso = f'{cliente.name} no tiene movimientos {periodo}, así que el extracto saldría vacío.'
        if not self.env.company.currency_id.is_zero(extracto['saldo_gs']):
            aviso += (f'\nSu saldo en esas fechas es Gs {formatLang(self.env, extracto["saldo_gs"], digits=0)}'
                      f' · USD {formatLang(self.env, extracto["saldo_usd"], digits=2)}.')
        return aviso + '\nProbá con otras fechas.'
