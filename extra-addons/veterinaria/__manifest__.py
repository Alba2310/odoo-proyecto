# -*- coding: utf-8 -*-
{
    'name': 'Patitas',
    'summary': 'Veterinaria: mascotas y sus dueños, historia clínica, vacunas, baño y peluquería, internación y hotel',
    'description': """
Patitas: sistema para veterinarias
==================================
* Hoy en Patitas: tablero de la recepción con la sala de espera (turnos de hoy, en espera, en atención y
  listas para retirar), los internados y hospedados, y las vacunas para avisar.
* Ficha de cada mascota con su dueño, especie, raza, edad, alertas ("muerde") y una línea de tiempo con todo lo
  que se le hizo, más el gráfico de su peso.
* Historia clínica en cada atención del consultorio: motivo, signos vitales, diagnóstico, tratamiento e
  indicaciones para la casa (se imprimen).
* Vacunas y desparasitaciones: al terminar la atención quedan registradas con la fecha de la próxima dosis.
  Aviso al dueño por WhatsApp con un clic (todas sus mascotas en un mensaje) y por correo. Carnet de vacunas.
* Baño y peluquería con su propia agenda y el aviso de "ya está lista para retirar" por WhatsApp.
* Internación y hotel: lugar (jaula, canil), controles del día, parte al dueño por WhatsApp y cobro por día.
* Cobro con factura, en efectivo, tarjeta, transferencia o una parte con cada uno (pago mixto).
* Venta de alimentos, medicamentos y accesorios con stock, compras a proveedores y stock mínimo.
* Turnos por internet: una página tipo chat (/reservar) donde el dueño pide el turno para su mascota.
""",
    'version': '18.0.1.0.0',
    'category': 'Services',
    'license': 'LGPL-3',
    'depends': ['account', 'purchase_stock', 'hr'],
    'data': [
        'security/veterinaria_security.xml',
        'security/ir.model.access.csv',
        'data/sequences.xml',
        'data/especies.xml',
        'data/product_data.xml',
        'data/resource_data.xml',
        'data/mail_template.xml',
        'data/cron.xml',
        'wizard/cobro_wizard_views.xml',
        'views/mascota_views.xml',
        'views/atencion_views.xml',
        'views/aplicacion_views.xml',
        'views/internacion_views.xml',
        'views/venta_views.xml',
        'views/product_views.xml',
        'views/hr_employee_views.xml',
        'views/res_partner_views.xml',
        'views/reportes_views.xml',
        'views/report_templates.xml',
        'views/reserva_templates.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'veterinaria/static/src/**/*',
        ],
    },
    'application': True,
    'installable': True,
}
