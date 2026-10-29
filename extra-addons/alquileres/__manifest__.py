# -*- coding: utf-8 -*-
{
    'name': 'Óga · Alquileres',
    'summary': 'Control de alquileres: contratos, cobros con aviso por WhatsApp, gastos, ganancia, mantenimiento y '
               'página "Se alquila"',
    'description': """
Óga: control de alquileres para el dueño o el administrador de las viviendas
=============================================================================
* Propiedades (casas y edificios) y sus unidades: una casa se alquila entera; un edificio, por departamento.
* Contratos: inquilino, garante, alquiler, día de pago, depósito, reajuste anual y renovación. Contrato en PDF
  listo para firmar.
* Las cuotas de cada mes se crean solas, con los cargos extra (ANDE, agua, reparaciones) que paga el inquilino.
* Pagos totales o parciales, con foto del comprobante y recibo numerado en PDF (con el monto en letras).
* Avisos por WhatsApp al inquilino: de pago (3 días antes, el día que vence y cada 3 días si no paga), de que
  vence el contrato y del reajuste. El sistema arma el mensaje y abre WhatsApp; solo falta tocar Enviar.
* Gastos de cada propiedad y ganancia real por mes; Panel con cobranza, deuda, ocupación y lo que hay que atender.
* Pedidos de mantenimiento: al resolverlos, el costo va a los gastos y, si lo paga el inquilino, a su cuota.
* Actas de entrada y salida con fotos y lecturas de medidores; al terminar el contrato, el depósito paga lo que
  quedó debiendo y se descuentan los daños.
* Puntaje de cada inquilino según cómo paga.
* Página pública "Se alquila" con las unidades libres; los interesados consultan por WhatsApp o dejan sus datos.
""",
    'version': '18.0.2.0.0',
    'category': 'Services',
    'license': 'LGPL-3',
    'depends': ['mail'],
    'data': [
        'security/alquiler_security.xml',
        'security/ir.model.access.csv',
        'data/sequences.xml',
        'data/cron.xml',
        'views/report_recibo.xml',
        'views/report_contrato.xml',
        'views/pago_views.xml',
        'views/cuota_views.xml',
        'views/acta_views.xml',
        'views/contrato_views.xml',
        'views/propiedad_views.xml',
        'views/gasto_views.xml',
        'views/mantenimiento_views.xml',
        'views/interesado_views.xml',
        'views/res_partner_views.xml',
        'views/wizard_views.xml',
        'views/se_alquila_templates.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'alquileres/static/src/**/*',
        ],
    },
    'application': True,
    'installable': True,
}
