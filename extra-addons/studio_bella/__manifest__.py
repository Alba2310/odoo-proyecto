# -*- coding: utf-8 -*-
{
    'name': 'Studio Bella',
    'summary': 'Peluquería: agenda de citas con estilistas, venta de productos y cobro con factura',
    'description': """
Sistema de gestión de la peluquería Studio Bella
================================================
* Agenda de citas en calendario, con un color por estilista. No deja agendar dos citas del mismo
  estilista a la misma hora, fuera de su horario de trabajo ni servicios que el estilista no hace.
* Catálogo de servicios (cortes, coloración, tratamientos, peinados, barbería, manos y pies) con
  precio, duración y los insumos que gasta cada uno (tinte, oxidante, keratina...).
* Venta de productos (shampoo, acondicionador, ceras...) dentro de la cita o en el mostrador,
  con el stock del inventario de Odoo.
* Cobro en efectivo, tarjeta o transferencia: emite la factura, registra el pago, calcula el
  vuelto y descuenta del stock lo vendido y los insumos usados.
* Recordatorio automático por correo al cliente el día antes de su cita, y por WhatsApp con un clic
  para los clientes que no tienen correo.
* Compras a proveedores y recepción de mercadería, con stock mínimo y aviso para reponer.
* Turnos por internet: una página (/turnos) donde las clientas eligen servicios, estilista, día y hora
  libres, y el turno entra solo a la agenda.
* Cierre de caja del día: lo cobrado en efectivo, tarjeta y transferencia, y el arqueo del efectivo
  (cuadra, sobra o falta). Con la caja cerrada no se cobra con esa fecha.
* Reportes de servicios realizados por estilista y de productos vendidos.
""",
    'version': '18.0.1.1.0',
    'category': 'Services',
    'license': 'LGPL-3',
    'depends': ['account', 'purchase_stock', 'hr'],
    'data': [
        'security/bella_security.xml',
        'security/ir.model.access.csv',
        'data/sequences.xml',
        'data/product_data.xml',
        'data/resource_data.xml',
        'data/mail_template.xml',
        'data/cron.xml',
        'wizard/cobro_wizard_views.xml',
        'views/cita_views.xml',
        'views/venta_views.xml',
        'views/product_views.xml',
        'views/hr_employee_views.xml',
        'views/res_partner_views.xml',
        'views/report_views.xml',
        'views/cierre_caja_views.xml',
        'views/turnos_templates.xml',
        'views/manual_views.xml',
        'views/menus.xml',
    ],
    'demo': [
        'demo/demo_data.xml',
        'demo/demo_compras.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'studio_bella/static/src/**/*',
        ],
    },
    'application': True,
    'installable': True,
}
