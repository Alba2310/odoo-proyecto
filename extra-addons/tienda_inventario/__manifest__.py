# -*- coding: utf-8 -*-
{
    'name': 'Tienda - Inventario',
    'summary': 'Productos, stock, reposición y ajustes de inventario',
    'description': """
Inventario básico para una tienda
=================================
* Catálogo de productos con código, categoría, costo y precio de venta.
* Stock calculado a partir de los movimientos (entradas y salidas).
* Reposición de mercadería y ajuste por conteo físico.
* Alerta de stock bajo.
* Productos de ejemplo precargados.
* Precios en guaraníes con IVA incluido (10 %, 5 % o exenta).
* Manual de uso en el menú Inventario > Manual de uso.

Al instalarse pone el guaraní (PYG) como moneda de la compañía.
""",
    'version': '18.0.1.1.0',
    'category': 'Inventory',
    'license': 'LGPL-3',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/movimiento_stock_wizard_views.xml',
        'views/producto_views.xml',
        'views/categoria_views.xml',
        'views/movimiento_views.xml',
        'views/menus.xml',
        'data/datos_iniciales.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'application': True,
    'installable': True,
}
