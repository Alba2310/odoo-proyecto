# -*- coding: utf-8 -*-
from odoo import api, fields, models

# Tasas de IVA de Paraguay. Los precios de venta ya incluyen el IVA.
TIPOS_IVA = [
    ('10', '10 %'),
    ('5', '5 %'),
    ('exenta', 'Exenta'),
]


class TiendaProducto(models.Model):
    _name = 'tienda.producto'
    _description = 'Producto'
    _order = 'name'

    name = fields.Char('Nombre', required=True)
    codigo = fields.Char('Código', required=True, copy=False)
    # Cada sucursal tiene su propio catálogo: el mismo artículo puede tener otra marca,
    # unidad o precio en cada una.
    sucursal_id = fields.Many2one('tienda.sucursal', string='Sucursal', required=True, index=True,
                                  default=lambda self: self.env.user.tienda_sucursal_id)
    marca = fields.Char('Marca')
    categoria_id = fields.Many2one('tienda.categoria', string='Categoría')
    unidad = fields.Selection([
        ('unidad', 'Unidad'),
        ('paquete', 'Paquete'),
        ('caja', 'Caja'),
        ('kg', 'Kilogramo'),
        ('litro', 'Litro'),
    ], string='Unidad de medida', default='unidad', required=True)
    descripcion = fields.Text('Descripción')
    active = fields.Boolean('Activo', default=True)

    currency_id = fields.Many2one(
        'res.currency', string='Moneda', required=True,
        default=lambda self: self.env.company.currency_id)
    costo = fields.Monetary('Costo')
    precio_venta = fields.Monetary('Precio de venta', required=True, help='Precio final al público, con IVA incluido.')
    iva = fields.Selection(TIPOS_IVA, string='IVA', required=True, default='10',
                           help='10 % para la mayoría de los productos; 5 % para los de la canasta básica.')

    movimiento_ids = fields.One2many('tienda.movimiento', 'producto_id', string='Movimientos')
    stock_despensa = fields.Float('En despensa', compute='_compute_stock', store=True,
                                  help='Lo que hay para vender en la despensa.')
    stock_deposito = fields.Float('En depósito', compute='_compute_stock', store=True)
    stock = fields.Float('Stock total', compute='_compute_stock', store=True)
    stock_minimo = fields.Float('Stock mínimo', default=5,
                                help='Cuando el stock total llega a este número, el producto se marca como "stock bajo".')
    stock_bajo = fields.Boolean('Stock bajo', compute='_compute_stock', store=True)
    valor_stock = fields.Monetary('Valor del stock (al costo)', compute='_compute_valor_stock')

    _sql_constraints = [
        ('codigo_uniq', 'unique(codigo, sucursal_id)', 'Ya existe un producto con ese código en la sucursal.'),
        ('precio_no_negativo', 'CHECK(precio_venta >= 0)', 'El precio de venta no puede ser negativo.'),
    ]

    @api.depends('movimiento_ids.cantidad', 'movimiento_ids.ubicacion', 'stock_minimo')
    def _compute_stock(self):
        for producto in self:
            movimientos = producto.movimiento_ids
            producto.stock_despensa = sum(movimientos.filtered(lambda m: m.ubicacion == 'despensa').mapped('cantidad'))
            producto.stock_deposito = sum(movimientos.filtered(lambda m: m.ubicacion == 'deposito').mapped('cantidad'))
            producto.stock = producto.stock_despensa + producto.stock_deposito
            producto.stock_bajo = producto.stock <= producto.stock_minimo

    @api.depends('stock', 'costo')
    def _compute_valor_stock(self):
        for producto in self:
            producto.valor_stock = producto.stock * producto.costo

    @api.depends('name', 'marca')
    def _compute_display_name(self):
        for producto in self:
            producto.display_name = f'{producto.name} ({producto.marca})' if producto.marca else producto.name

    def _stock_en(self, ubicacion):
        self.ensure_one()
        return self.stock_despensa if ubicacion == 'despensa' else self.stock_deposito

    def action_reponer(self):
        return self._abrir_asistente_stock('reponer', 'Reponer stock')

    def action_ajustar(self):
        return self._abrir_asistente_stock('ajustar', 'Ajustar stock')

    def action_transferir(self):
        return self._abrir_asistente_stock('transferir', 'Pasar mercadería')

    def _abrir_asistente_stock(self, modo, titulo):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': titulo,
            'res_model': 'tienda.movimiento.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_producto_id': self.id, 'default_modo': modo},
        }
