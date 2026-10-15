# -*- coding: utf-8 -*-
from odoo import fields, models


class TiendaCategoria(models.Model):
    _name = 'tienda.categoria'
    _description = 'Categoría de producto'
    _order = 'name'

    name = fields.Char('Nombre', required=True)
    producto_ids = fields.One2many('tienda.producto', 'categoria_id', string='Productos')
    producto_count = fields.Integer('Cant. de productos', compute='_compute_producto_count')

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Ya existe una categoría con ese nombre.'),
    ]

    def _compute_producto_count(self):
        for categoria in self:
            categoria.producto_count = len(categoria.producto_ids)
