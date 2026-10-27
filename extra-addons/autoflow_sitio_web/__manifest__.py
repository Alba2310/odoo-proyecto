# -*- coding: utf-8 -*-
{
    'name': 'Solicitudes de los sitios web (AutoFlow y Studio Bella)',
    'summary': 'Recibe en el CRM las solicitudes de demo de los sitios web de AutoFlow y Studio Bella y avisa por correo',
    'description': """
Solicitudes de los sitios web
=============================
* Ruta pública ``POST /autoflow/solicitud`` que usan los formularios de ``sitio-web/contacto.html`` (AutoFlow)
  y ``sitio-bella/contacto.html`` (Studio Bella, que manda ``producto=studio_bella``).
* Cada solicitud se guarda como oportunidad del CRM con la etiqueta "Sitio web" y la del producto.
* Envía un correo de aviso a la dirección del parámetro del sistema ``autoflow_sitio_web.email_aviso``
  (si no está cargado, al correo de la compañía).
""",
    'version': '18.0.1.0.0',
    'category': 'Sales/CRM',
    'license': 'LGPL-3',
    'depends': ['crm'],
    'data': [
        'data/crm_data.xml',
    ],
    'installable': True,
}
