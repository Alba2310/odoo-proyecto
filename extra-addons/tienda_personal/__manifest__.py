# -*- coding: utf-8 -*-
{
    'name': 'Tienda - Personal',
    'summary': 'Empleados, asistencia, faltas, reposos, bonos, sanciones y pagos por hora',
    'description': """
Personal de la tienda
=====================
* Empleados por sucursal, con su pago por hora y los días que trabajan.
* Asistencia: entrada y salida de cada día, con cálculo de horas.
* Faltas automáticas: si un empleado no marca entrada un día que le toca trabajar,
  el sistema lo marca como falta (o como reposo, si tiene un reposo cargado).
* Reposos con fecha desde/hasta y certificado.
* Bonos y sanciones. No corresponde bono a quien faltó sin aviso en el mes.
* Pagos: junta las horas trabajadas, los bonos y las sanciones pendientes y
  emite un recibo para firmar.
* Panel con lo que se le debe a cada empleado y si le corresponde el bono.
* Manual de uso en el menú Personal > Manual de uso.
""",
    'version': '18.0.1.0.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'depends': ['tienda_ventas'],
    'data': [
        'security/ir.model.access.csv',
        'data/secuencia.xml',
        'data/cron.xml',
        'report/recibo_pago.xml',
        'views/empleado_views.xml',
        'views/asistencia_views.xml',
        'views/reposo_views.xml',
        'views/ajuste_views.xml',
        'views/pago_views.xml',
        'views/menus.xml',
    ],
    'application': True,
    'installable': True,
}
