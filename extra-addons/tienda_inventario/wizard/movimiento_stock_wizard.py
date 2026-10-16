# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

from ..models.sucursal import UBICACIONES

NOMBRE_UBICACION = dict(UBICACIONES)
OTRA_UBICACION = {'despensa': 'deposito', 'deposito': 'despensa'}


class TiendaMovimientoWizard(models.TransientModel):
    _name = 'tienda.movimiento.wizard'
    _description = 'Asistente para reponer, ajustar o pasar stock'

    producto_id = fields.Many2one('tienda.producto', string='Producto', required=True)
    modo = fields.Selection([
        ('reponer', 'Reponer (entra mercadería)'),
        ('transferir', 'Pasar entre depósito y despensa'),
        ('ajustar', 'Ajustar al stock contado'),
    ], string='Operación', required=True, default='reponer')
    ubicacion = fields.Selection(UBICACIONES, string='Ubicación', required=True,
                                 compute='_compute_ubicacion', store=True, readonly=False, precompute=True,
                                 help='Al pasar mercadería, es el lugar de donde sale.')
    destino = fields.Char('Hacia', compute='_compute_destino')
    stock_despensa = fields.Float(related='producto_id.stock_despensa')
    stock_deposito = fields.Float(related='producto_id.stock_deposito')
    cantidad = fields.Float('Cantidad')
    stock_contado = fields.Float('Stock contado')
    referencia = fields.Char('Referencia',
                             help='Por ejemplo: número de factura del proveedor o motivo del ajuste.')

    @api.depends('modo')
    def _compute_ubicacion(self):
        # Lo que llega del proveedor va al depósito, y del depósito pasa a la despensa.
        for asistente in self:
            asistente.ubicacion = 'despensa' if asistente.modo == 'ajustar' else 'deposito'

    @api.depends('ubicacion')
    def _compute_destino(self):
        for asistente in self:
            asistente.destino = NOMBRE_UBICACION.get(OTRA_UBICACION.get(asistente.ubicacion), '')

    def action_confirmar(self):
        self.ensure_one()
        producto, ubicacion = self.producto_id, self.ubicacion
        Movimiento = self.env['tienda.movimiento']
        if self.modo == 'reponer':
            if self.cantidad <= 0:
                raise UserError('La cantidad a reponer debe ser mayor que cero.')
            Movimiento.create({'producto_id': producto.id, 'ubicacion': ubicacion, 'tipo': 'reposicion',
                               'cantidad': self.cantidad, 'referencia': self.referencia})
        elif self.modo == 'transferir':
            disponible = producto._stock_en(ubicacion)
            if self.cantidad <= 0:
                raise UserError('La cantidad a pasar debe ser mayor que cero.')
            if self.cantidad > disponible:
                raise UserError(f'En {NOMBRE_UBICACION[ubicacion].lower()} hay {disponible:g}: '
                                f'no se pueden pasar {self.cantidad:g}.')
            destino = OTRA_UBICACION[ubicacion]
            referencia = self.referencia or f'{NOMBRE_UBICACION[ubicacion]} → {NOMBRE_UBICACION[destino]}'
            Movimiento.create([
                {'producto_id': producto.id, 'ubicacion': ubicacion, 'tipo': 'transferencia',
                 'cantidad': -self.cantidad, 'referencia': referencia},
                {'producto_id': producto.id, 'ubicacion': destino, 'tipo': 'transferencia',
                 'cantidad': self.cantidad, 'referencia': referencia},
            ])
        else:
            if self.stock_contado < 0:
                raise UserError('El stock contado no puede ser negativo.')
            diferencia = self.stock_contado - producto._stock_en(ubicacion)
            if not diferencia:
                raise UserError('El stock contado es igual al stock actual: no hay nada que ajustar.')
            Movimiento.create({'producto_id': producto.id, 'ubicacion': ubicacion, 'tipo': 'ajuste',
                               'cantidad': diferencia, 'referencia': self.referencia})
        return {'type': 'ir.actions.act_window_close'}
