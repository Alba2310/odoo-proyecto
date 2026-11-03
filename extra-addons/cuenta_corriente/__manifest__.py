# -*- coding: utf-8 -*-
{
    'name': 'Cuenta corriente en guaraníes y dólares',
    'summary': 'Cuenta corriente de cada cliente con el Debe, el Haber y el saldo en guaraníes y en dólares, y su '
               'extracto en PDF',
    'description': """
Cuenta corriente en guaraníes y dólares
=======================================
* Clientes con su saldo en guaraníes y en dólares, y quiénes tienen saldo pendiente.
* Los movimientos de cada cliente (facturas, cobros, notas de crédito y ajustes por cotización), dichos en
  palabras, con el Debe, el Haber y el saldo en guaraníes y en dólares.
* Lo que se hizo en dólares pasa a guaraníes con la cotización del día del movimiento (la misma que usa la
  contabilidad de Odoo); lo que se hizo en guaraníes pasa a dólares con la cotización de ese día.
* Extracto de cuenta en PDF por cliente y período, para imprimir o mandar.
* La factura y el recibo de cobro en PDF muestran el total en guaraníes y en dólares, con la cotización.
* Cotizaciones del dólar: una por día, en guaraníes por cada dólar. La referencial del BCP se carga sola todos
  los días (de DolarPy) o con un botón.
""",
    'version': '18.0.1.1.0',
    'category': 'Accounting/Accounting',
    'license': 'LGPL-3',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'data/cron.xml',
        'views/report_extracto.xml',
        'views/report_dos_monedas.xml',
        'views/extracto_views.xml',
        'views/cuenta_corriente_views.xml',
        'views/cotizacion_views.xml',
        'views/res_partner_views.xml',
        'views/menus.xml',
    ],
    'application': True,
    'installable': True,
}
