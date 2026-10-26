# -*- coding: utf-8 -*-
{
    'name': 'AutoFlow · Solicitudes del sitio web',
    'summary': 'Recibe en el CRM las solicitudes de demo del sitio web de AutoFlow y avisa por correo',
    'description': """
Solicitudes del sitio web de AutoFlow
=====================================
* Ruta pública ``POST /autoflow/solicitud`` que usa el formulario de ``sitio-web/contacto.html``.
* Cada solicitud se guarda como oportunidad del CRM con la etiqueta "Sitio web".
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
