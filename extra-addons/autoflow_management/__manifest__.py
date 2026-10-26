# -*- coding: utf-8 -*-
{
    'name': 'AutoFlow ERP',
    'summary': 'Concesionario y taller: vehículos, pruebas de manejo, órdenes de servicio y entregas',
    'description': """
Gestión avanzada de concesionario y taller
==========================================
* Vehículos con marca, modelo, año, chasis (VIN), kilometraje, estado, costos y galería de fotos.
* Pruebas de manejo vinculadas al cliente y a la oportunidad del CRM, con control de
  combustible y kilometraje, calendario y validación de solapamientos.
* Órdenes de servicio (OS/2026/0001) con flujo kanban, repuestos del inventario de Odoo,
  horas de mano de obra y checklist de inspección de entrega.
* Catálogo de repuestos de taller precargado: lubricantes, filtros, frenos, suspensión,
  motor y eléctrico.
* Asistente de recepción de vehículos con nivel de combustible y daños visibles.
* Al pasar a "Listo para entrega" se avisa al cliente por correo; al finalizar se descuentan
  los repuestos del stock y se genera la factura en borrador.
* Venta de vehículos desde una cotización: al confirmarla el vehículo queda vendido.
* Reporte PDF "Orden de servicio y acta de entrega" con firma del cliente.
* Análisis de modelos con más fallas y de órdenes cerradas por mecánico.
""",
    'version': '18.0.1.0.0',
    'category': 'Services',
    'license': 'LGPL-3',
    'depends': ['sale_crm', 'sale_stock', 'account', 'hr'],
    'data': [
        'security/autoflow_security.xml',
        'security/ir.model.access.csv',
        'data/sequences.xml',
        'data/product_data.xml',
        'data/workshop_parts_data.xml',
        'data/inspection_data.xml',
        'data/mail_template.xml',
        'report/workshop_order_report.xml',
        'wizard/vehicle_reception_wizard_views.xml',
        'views/vehicle_views.xml',
        'views/test_drive_views.xml',
        'views/workshop_order_views.xml',
        'views/inspection_views.xml',
        'views/analysis_views.xml',
        'views/crm_lead_views.xml',
        'views/sale_order_views.xml',
        'views/product_views.xml',
        'views/menus.xml',
    ],
    'demo': [
        'demo/demo_data.xml',
        'demo/workshop_parts_stock.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'autoflow_management/static/src/**/*',
        ],
    },
    'application': True,
    'installable': True,
}
