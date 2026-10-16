# -*- coding: utf-8 -*-
from odoo import fields, models

# Cada sucursal tiene una despensa (donde se vende) y un depósito (donde se guarda).
UBICACIONES = [
    ('despensa', 'Despensa'),
    ('deposito', 'Depósito'),
]


class TiendaSucursal(models.Model):
    _name = 'tienda.sucursal'
    _description = 'Sucursal'
    _order = 'name'

    name = fields.Char('Nombre', required=True)
    direccion = fields.Char('Dirección')
    telefono = fields.Char('Teléfono')
    active = fields.Boolean('Activa', default=True)
    producto_ids = fields.One2many('tienda.producto', 'sucursal_id', string='Productos')
    producto_count = fields.Integer('Cant. de productos', compute='_compute_producto_count')

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Ya existe una sucursal con ese nombre.'),
    ]

    def _compute_producto_count(self):
        for sucursal in self:
            sucursal.producto_count = len(sucursal.producto_ids)


class ResUsers(models.Model):
    _inherit = 'res.users'

    tienda_sucursal_id = fields.Many2one(
        'tienda.sucursal', string='Sucursal',
        help='Sucursal donde trabaja el usuario. Se usa como sucursal por defecto en productos, cajas y ventas.')
