# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class TiendaAjuste(models.Model):
    """Bono (se suma al pago) o sanción (se resta). Los bonos los elige el dueño."""
    _name = 'tienda.ajuste'
    _description = 'Bono o sanción'
    _order = 'fecha desc, id desc'

    empleado_id = fields.Many2one('tienda.empleado', string='Empleado', required=True,
                                  ondelete='cascade', index=True)
    sucursal_id = fields.Many2one(related='empleado_id.sucursal_id', store=True, string='Sucursal')
    tipo = fields.Selection([('bono', 'Bono'), ('sancion', 'Sanción')], string='Tipo',
                            required=True, default='bono')
    fecha = fields.Date('Fecha', required=True, default=fields.Date.context_today)
    motivo = fields.Char('Motivo', required=True)
    currency_id = fields.Many2one(related='empleado_id.currency_id')
    monto = fields.Monetary('Monto', help='En una sanción, lo que se descuenta del pago. Puede ser 0 '
                                          '(por ejemplo, un llamado de atención).')
    pago_id = fields.Many2one('tienda.pago', string='Pago', readonly=True, ondelete='set null', index=True)
    pagado = fields.Boolean('Pagado', compute='_compute_pagado', store=True)
    corresponde_bono = fields.Boolean(related='empleado_id.corresponde_bono')
    faltas_mes = fields.Integer(related='empleado_id.faltas_mes')

    @api.depends('pago_id.estado')
    def _compute_pagado(self):
        for ajuste in self:
            ajuste.pagado = ajuste.pago_id.estado == 'pagado'

    @api.constrains('tipo', 'monto')
    def _check_monto(self):
        for ajuste in self:
            if ajuste.monto < 0:
                raise ValidationError('El monto no puede ser negativo.')
            if ajuste.tipo == 'bono' and not ajuste.monto:
                raise ValidationError('El bono tiene que tener un monto.')

    def write(self, vals):
        if set(vals) - {'pago_id'} and any(self.mapped('pagado')):
            raise UserError('No se puede modificar un bono o sanción que ya se pagó. Anule el pago primero.')
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_excepto_pagados(self):
        if any(self.mapped('pagado')):
            raise UserError('No se puede eliminar un bono o sanción que ya se pagó. Anule el pago primero.')
