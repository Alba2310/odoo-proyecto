# -*- coding: utf-8 -*-


def pasar_a_guaranies(env):
    """La tienda trabaja en guaraníes: activa la moneda, la pone como moneda de la
    compañía y la asigna a los productos que todavía tengan otra moneda."""
    pyg = env.ref('base.PYG')
    pyg.active = True
    compania = env.ref('base.main_company')
    if compania.currency_id != pyg:
        compania.currency_id = pyg
    productos = env['tienda.producto'].with_context(active_test=False).search([('currency_id', '!=', pyg.id)])
    productos.currency_id = pyg


def post_init_hook(env):
    pasar_a_guaranies(env)
