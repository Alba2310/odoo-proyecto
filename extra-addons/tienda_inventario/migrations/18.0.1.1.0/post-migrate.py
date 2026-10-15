# -*- coding: utf-8 -*-
"""Versión 1.1: la tienda pasa de dólares a guaraníes y los productos tienen IVA.

Los productos precargados se crearon con precios en dólares; acá se reemplazan por
precios en guaraníes (los mismos de data/datos_iniciales.xml) y su tasa de IVA."""
from odoo import SUPERUSER_ID, api

from odoo.addons.tienda_inventario.hooks import pasar_a_guaranies

# xmlid: (costo, precio de venta, IVA)
PRECIOS = {
    'producto_arroz': (6500, 8500, '5'),
    'producto_fideos': (4500, 6000, '5'),
    'producto_azucar': (5800, 7500, '5'),
    'producto_aceite': (13500, 17000, '5'),
    'producto_yerba': (15000, 19000, '5'),
    'producto_harina': (5000, 6500, '5'),
    'producto_sal': (2500, 3500, '5'),
    'producto_cafe': (25000, 32000, '10'),
    'producto_gaseosa': (10000, 13000, '10'),
    'producto_agua': (4200, 6000, '10'),
    'producto_jugo': (7500, 10000, '10'),
    'producto_leche': (5800, 7500, '5'),
    'producto_huevos': (11000, 14000, '5'),
    'producto_jabon_polvo': (17000, 22000, '10'),
    'producto_lavandina': (4800, 6500, '10'),
    'producto_papel': (9000, 12000, '10'),
    'producto_jabon_tocador': (3600, 5000, '10'),
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    pasar_a_guaranies(env)
    for xmlid, (costo, precio, iva) in PRECIOS.items():
        producto = env.ref(f'tienda_inventario.{xmlid}', raise_if_not_found=False)
        if producto:
            producto.write({'costo': costo, 'precio_venta': precio, 'iva': iva})
