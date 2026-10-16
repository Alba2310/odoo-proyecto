# -*- coding: utf-8 -*-
"""Versión 1.2: sucursales con despensa y depósito.

Todo lo que existía antes (productos y su stock) era de la despensa de Areguá."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    aregua = env.ref('tienda_inventario.sucursal_aregua')
    productos = env['tienda.producto'].with_context(active_test=False)
    productos.search([('sucursal_id', '=', False)]).sucursal_id = aregua
    env['tienda.movimiento'].search([('ubicacion', '=', False)]).ubicacion = 'despensa'
    # Recalcular el stock separado por despensa y depósito de todos los productos.
    todos = productos.search([])
    for campo in ('stock_despensa', 'stock_deposito', 'stock', 'stock_bajo'):
        env.add_to_compute(todos._fields[campo], todos)
    env.flush_all()
