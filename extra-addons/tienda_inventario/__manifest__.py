# -*- coding: utf-8 -*-
{
    'name': 'Tienda - Inventario',
    'summary': 'Productos por sucursal, despensa y depósito, reposición y ajustes de stock',
    'description': """
Inventario básico para una tienda con sucursales
================================================
* Sucursales (Areguá y Capiatá), cada una con su despensa y su depósito.
* Catálogo de productos por sucursal, con marca, código, categoría, costo y precio.
* Stock separado en despensa y depósito, calculado a partir de los movimientos.
* Reposición de mercadería, paso del depósito a la despensa y ajuste por conteo físico.
* Alerta de stock bajo.
* Productos de ejemplo precargados para cada sucursal.
* Precios en guaraníes con IVA incluido (10 %, 5 % o exenta).
* Manual de uso en el menú Inventario > Manual de uso.

Al instalarse pone el guaraní (PYG) como moneda de la compañía.
""",
    'version': '18.0.1.2.0',
    'category': 'Inventory',
    'license': 'LGPL-3',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'data/sucursales.xml',
        'wizard/movimiento_stock_wizard_views.xml',
        'views/producto_views.xml',
        'views/categoria_views.xml',
        'views/movimiento_views.xml',
        'views/sucursal_views.xml',
        'views/menus.xml',
        'data/datos_iniciales.xml',
        'data/productos_capiata.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'application': True,
    'installable': True,
}
