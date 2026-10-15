# -*- coding: utf-8 -*-
{
    'name': 'Tienda - Ventas',
    'summary': 'Ventas, caja e IVA con descuento automático del stock',
    'description': """
Ventas básicas para una tienda
==============================
* Registro de ventas con varios productos, precio y descuento (%) por línea.
* Al confirmar la venta se descuenta el stock y queda el movimiento registrado.
* Control de stock insuficiente.
* Cancelar una venta devuelve los productos al stock.
* Forma de pago (efectivo, tarjeta, transferencia / QR) y cálculo del vuelto.
* IVA incluido en el precio (10 %, 5 % o exenta) y su liquidación.
* Apertura y cierre de caja con conteo del efectivo.
* Ticket de venta y resumen de cierre para impresora térmica de 80 mm.
* Reporte de productos vendidos.
* Manual de uso en el menú Ventas > Manual de uso.
""",
    'version': '18.0.1.2.0',
    'category': 'Sales',
    'license': 'LGPL-3',
    'depends': ['tienda_inventario'],
    'data': [
        'security/ir.model.access.csv',
        'data/secuencia.xml',
        'report/ticket_venta.xml',
        'report/ticket_cierre_caja.xml',
        'views/venta_views.xml',
        'views/caja_views.xml',
        'views/movimiento_views.xml',
        'views/menus.xml',
    ],
    'application': True,
    'installable': True,
}
