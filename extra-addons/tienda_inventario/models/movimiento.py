# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class TiendaMovimiento(models.Model):
    """Cada entrada o salida de mercadería. El stock de un producto es la suma
    de sus movimientos, por eso no se editan ni se borran (ver permisos)."""
    _name = 'tienda.movimiento'
    _description = 'Movimiento de stock'
    _order = 'fecha desc, id desc'

    fecha = fields.Datetime('Fecha', default=fields.Datetime.now, required=True)
    producto_id = fields.Many2one('tienda.producto', string='Producto', required=True,
                                  ondelete='cascade', index=True)
    tipo = fields.Selection([
        ('inicial', 'Stock inicial'),
        ('reposicion', 'Reposición'),
        ('ajuste', 'Ajuste de inventario'),
    ], string='Tipo', required=True, default='ajuste')
    cantidad = fields.Float('Cantidad', required=True,
                            help='Positiva cuando entra mercadería, negativa cuando sale.')
    saldo = fields.Float('Stock resultante', readonly=True,
                         help='Stock del producto inmediatamente después de este movimiento.')
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
        # Saldo acumulado por producto, para que varios movimientos del mismo
        # producto creados juntos (por ejemplo una venta) queden encadenados.
        saldos = {}
        productos = self.env['tienda.producto']
        for vals in vals_list:
            producto_id = vals.get('producto_id')
            if producto_id not in saldos:
                saldos[producto_id] = productos.browse(producto_id).stock if producto_id else 0
            saldos[producto_id] += vals.get('cantidad', 0)
            vals['saldo'] = saldos[producto_id]
        return super().create(vals_list)
