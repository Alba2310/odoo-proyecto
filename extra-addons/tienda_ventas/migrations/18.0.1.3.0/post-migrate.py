# -*- coding: utf-8 -*-
"""Versión 1.3: ventas y cajas por sucursal. Lo anterior era todo de Areguá."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    aregua = env.ref('tienda_inventario.sucursal_aregua')
    env['tienda.venta'].search([('sucursal_id', '=', False)]).sucursal_id = aregua
    env['tienda.caja'].search([('sucursal_id', '=', False)]).sucursal_id = aregua
