# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.exceptions import UserError


class TiendaMovimientoWizard(models.TransientModel):
    _name = 'tienda.movimiento.wizard'
    _description = 'Asistente para reponer o ajustar stock'

    producto_id = fields.Many2one('tienda.producto', string='Producto', required=True)
    modo = fields.Selection([
        ('reponer', 'Reponer stock (entra mercadería)'),
        ('ajustar', 'Ajustar al stock contado'),
    ], string='Operación', required=True, default='reponer')
    stock_actual = fields.Float(related='producto_id.stock', string='Stock actual')
    cantidad = fields.Float('Cantidad que ingresa')
    stock_contado = fields.Float('Stock contado')
    referencia = fields.Char('Referencia',
                             help='Por ejemplo: número de factura del proveedor o motivo del ajuste.')

    def action_confirmar(self):
        self.ensure_one()
        if self.modo == 'reponer':
            if self.cantidad <= 0:
                raise UserError('La cantidad a reponer debe ser mayor que cero.')
            tipo, cantidad = 'reposicion', self.cantidad
        else:
            if self.stock_contado < 0:
                raise UserError('El stock contado no puede ser negativo.')
            tipo, cantidad = 'ajuste', self.stock_contado - self.producto_id.stock
            if not cantidad:
                raise UserError('El stock contado es igual al stock actual: no hay nada que ajustar.')
        self.env['tienda.movimiento'].create({
            'producto_id': self.producto_id.id,
            'tipo': tipo,
            'cantidad': cantidad,
            'referencia': self.referencia,
        })
        return {'type': 'ir.actions.act_window_close'}
