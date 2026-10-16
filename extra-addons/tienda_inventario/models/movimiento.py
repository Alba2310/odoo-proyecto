# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .sucursal import UBICACIONES


class TiendaMovimiento(models.Model):
    """Cada entrada o salida de mercadería. El stock de un producto es la suma
    de sus movimientos, por eso no se editan ni se borran (ver permisos)."""
    _name = 'tienda.movimiento'
    _description = 'Movimiento de stock'
    _order = 'fecha desc, id desc'

    fecha = fields.Datetime('Fecha', default=fields.Datetime.now, required=True)
    producto_id = fields.Many2one('tienda.producto', string='Producto', required=True,
                                  ondelete='cascade', index=True)
    sucursal_id = fields.Many2one(related='producto_id.sucursal_id', store=True, string='Sucursal')
    ubicacion = fields.Selection(UBICACIONES, string='Ubicación', required=True, default='despensa')
    tipo = fields.Selection([
        ('inicial', 'Stock inicial'),
        ('reposicion', 'Reposición'),
        ('ajuste', 'Ajuste de inventario'),
        ('transferencia', 'Paso entre depósito y despensa'),
    ], string='Tipo', required=True, default='ajuste')
    cantidad = fields.Float('Cantidad', required=True,
                            help='Positiva cuando entra mercadería, negativa cuando sale.')
    saldo = fields.Float('Stock resultante', readonly=True,
                         help='Stock de esa ubicación (despensa o depósito) justo después de este movimiento.')
    referencia = fields.Char('Referencia')
    usuario_id = fields.Many2one('res.users', string='Usuario',
                                 default=lambda self: self.env.user, readonly=True)

    @api.depends('producto_id', 'cantidad')
    def _compute_display_name(self):
        for movimiento in self:
            movimiento.display_name = f'{movimiento.producto_id.name} ({movimiento.cantidad:+g})'

    @api.constrains('cantidad')
    def _check_cantidad(self):
        for movimiento in self:
            if not movimiento.cantidad:
                raise ValidationError('La cantidad de un movimiento de stock no puede ser cero.')

    @api.model_create_multi
    def create(self, vals_list):
        # Saldo acumulado por producto y ubicación, para que varios movimientos del
        # mismo producto creados juntos (por ejemplo una venta) queden encadenados.
        saldos = {}
        productos = self.env['tienda.producto']
        for vals in vals_list:
            clave = (vals.get('producto_id'), vals.get('ubicacion') or 'despensa')
            if clave not in saldos:
                producto = productos.browse(clave[0])
                saldos[clave] = producto._stock_en(clave[1]) if clave[0] else 0
            saldos[clave] += vals.get('cantidad', 0)
            vals['saldo'] = saldos[clave]
        return super().create(vals_list)
