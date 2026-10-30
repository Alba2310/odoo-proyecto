# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_amount


class VetCobroWizard(models.TransientModel):
    """Caja: el total se reparte entre efectivo, tarjeta y transferencia (una parte con cada uno, si hace falta).
    Con el efectivo que entrega el dueño se calcula el vuelto."""
    _name = 'vet.cobro.wizard'
    _description = 'Cobrar'

    atencion_id = fields.Many2one('vet.atencion', string='Atención', readonly=True)
    internacion_id = fields.Many2one('vet.internacion', string='Estadía', readonly=True)
    venta_id = fields.Many2one('vet.venta', string='Venta', readonly=True)
    cliente_id = fields.Many2one('res.partner', string='Cliente', compute='_compute_documento')
    concepto = fields.Char('Concepto', compute='_compute_documento')
    currency_id = fields.Many2one('res.currency', compute='_compute_documento')
    total = fields.Monetary('Total', compute='_compute_documento')

    efectivo = fields.Monetary('Efectivo', compute='_compute_efectivo', store=True, readonly=False)
    tarjeta = fields.Monetary('Tarjeta')
    transferencia = fields.Monetary('Transferencia / QR')
    falta = fields.Monetary('Falta repartir', compute='_compute_falta')
    entrega = fields.Monetary('Entrega en efectivo', help='Con cuánto paga el dueño, para calcular el vuelto.')
    vuelto = fields.Monetary('Vuelto', compute='_compute_vuelto')

    def _documento(self):
        self.ensure_one()
        return self.atencion_id or self.internacion_id or self.venta_id

    @api.depends('atencion_id', 'internacion_id', 'venta_id')
    def _compute_documento(self):
        for wizard in self:
            documento = wizard._documento()
            wizard.cliente_id = documento.dueno_id
            wizard.currency_id = documento.currency_id or self.env.company.currency_id
            wizard.total = documento.total
            if wizard.atencion_id:
                wizard.concepto = f'{documento.mascota_id.name}: {documento.servicios_texto}'
            elif wizard.internacion_id:
                wizard.concepto = f'{documento.mascota_id.name}: {documento._tipo_texto().lower()} en {documento.lugar_id.name}'
            else:
                wizard.concepto = documento.name

    @api.depends('total', 'tarjeta', 'transferencia')
    def _compute_efectivo(self):
        # Lo que no se paga con tarjeta ni transferencia, en efectivo.
        for wizard in self:
            wizard.efectivo = max(wizard.total - wizard.tarjeta - wizard.transferencia, 0)

    @api.depends('total', 'efectivo', 'tarjeta', 'transferencia')
    def _compute_falta(self):
        for wizard in self:
            wizard.falta = wizard.total - wizard.efectivo - wizard.tarjeta - wizard.transferencia

    @api.depends('efectivo', 'entrega')
    def _compute_vuelto(self):
        for wizard in self:
            wizard.vuelto = max(wizard.entrega - wizard.efectivo, 0) if wizard.entrega else 0

    def _reabrir(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Cobrar',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_todo_tarjeta(self):
        self.write({'tarjeta': self.total, 'transferencia': 0, 'entrega': 0})
        return self._reabrir()

    def action_todo_transferencia(self):
        self.write({'tarjeta': 0, 'transferencia': self.total, 'entrega': 0})
        return self._reabrir()

    def action_todo_efectivo(self):
        self.write({'tarjeta': 0, 'transferencia': 0})
        return self._reabrir()

    def action_cobrar(self):
        self.ensure_one()
        documento = self._documento()
        if not documento:
            raise UserError('No hay nada para cobrar.')
        moneda = self.currency_id
        if not moneda.is_zero(self.falta):
            if moneda.compare_amounts(self.falta, 0) > 0:
                raise UserError(f'Faltan repartir {format_amount(self.env, self.falta, moneda)} entre las formas '
                                'de pago.')
            raise UserError('Las formas de pago suman más que el total.')
        if self.entrega and moneda.compare_amounts(self.entrega, self.efectivo) < 0:
            raise UserError('Lo que entrega en efectivo es menos de lo que tiene que pagar en efectivo.')
        documento._vet_cobrar({'efectivo': self.efectivo, 'tarjeta': self.tarjeta,
                               'transferencia': self.transferencia})
        return {'type': 'ir.actions.act_window_close'}
