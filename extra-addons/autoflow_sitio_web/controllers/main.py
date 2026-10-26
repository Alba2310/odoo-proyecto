# -*- coding: utf-8 -*-
import logging
import re

from markupsafe import Markup

from odoo import Command, http
from odoo.http import request

_logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]{2,}$')

# Campo del formulario y largo máximo que se acepta.
CAMPOS = {
    'nombre': 120,
    'empresa': 120,
    'telefono': 40,
    'email': 120,
    'tipo': 20,
    'usuarios': 20,
    'plan': 20,
    'mensaje': 2000,
}
TIPOS = {
    'concesionaria': 'Concesionaria',
    'taller': 'Taller mecánico',
    'ambos': 'Concesionaria con taller',
}
PLANES = {
    'inicial': 'Inicial',
    'profesional': 'Profesional',
    'empresa': 'Empresa',
}


class SolicitudSitioWeb(http.Controller):

    # cors='*' deja que el sitio, publicado en otra dirección, lea la respuesta.
    # El sitio manda el formulario como datos de formulario comunes, así el navegador no hace consulta previa.
    @http.route('/autoflow/solicitud', type='http', auth='public', methods=['POST', 'OPTIONS'],
                csrf=False, cors='*', save_session=False)
    def recibir_solicitud(self, **datos):
        # Campo trampa: está oculto en el formulario, así que solo lo completa un robot.
        if datos.get('sitio_web'):
            return request.make_json_response({'ok': True})

        valores = {campo: (datos.get(campo) or '').strip()[:largo] for campo, largo in CAMPOS.items()}
        errores = self._validar(valores)
        if errores:
            return request.make_json_response({'ok': False, 'errores': errores}, status=400)

        # Sin el aviso estándar "Te asignaron…": el correo propio ya lleva todos los datos.
        lead = request.env['crm.lead'].sudo().with_context(mail_auto_subscribe_no_notify=True).create(
            self._valores_oportunidad(valores))
        self._avisar_por_correo(lead)
        return request.make_json_response({'ok': True, 'referencia': lead.id})

    def _validar(self, valores):
        errores = []
        if len(valores['nombre']) < 3:
            errores.append('nombre')
        if len(valores['empresa']) < 2:
            errores.append('empresa')
        if len(re.sub(r'\D', '', valores['telefono'])) < 7:
            errores.append('telefono')
        if not EMAIL_RE.match(valores['email']):
            errores.append('email')
        return errores

    def _valores_oportunidad(self, valores):
        # La petición llega como "Usuario público", que no puede leer equipos ni usuarios.
        env = request.env(su=True)
        # Sin vendedor explícito, Odoo pondría al "Usuario público" que hace la petición.
        equipo = env.ref('sales_team.team_sales_department', raise_if_not_found=False)
        vendedor = (equipo and equipo.user_id) or env.ref('base.user_admin')
        detalle = [
            ('Tipo de negocio', TIPOS.get(valores['tipo'], 'Sin indicar')),
            ('Usuarios', valores['usuarios'] or 'Sin indicar'),
            ('Plan de interés', PLANES.get(valores['plan'], 'Todavía no sabe')),
            ('Mensaje', valores['mensaje'] or '—'),
        ]
        descripcion = Markup('<ul>%s</ul>') % Markup().join(
            Markup('<li><b>%s:</b> %s</li>') % (titulo, texto) for titulo, texto in detalle
        )
        medio = env.ref('utm.utm_medium_website', raise_if_not_found=False)
        return {
            'name': f"Demo AutoFlow · {valores['empresa']}",
            'type': 'opportunity',
            'contact_name': valores['nombre'],
            'partner_name': valores['empresa'],
            'email_from': valores['email'],
            'phone': valores['telefono'],
            'description': descripcion,
            'user_id': vendedor.id,
            'team_id': equipo.id if equipo else False,
            'tag_ids': [Command.link(env.ref('autoflow_sitio_web.tag_sitio_web').id)],
            'medium_id': medio.id if medio else False,
        }

    def _avisar_por_correo(self, lead):
        destino = (request.env['ir.config_parameter'].sudo().get_param('autoflow_sitio_web.email_aviso')
                   or lead.company_id.email or request.env.company.email)
        if not destino:
            _logger.warning('Solicitud %s sin aviso por correo: falta el parámetro autoflow_sitio_web.email_aviso', lead.id)
            return
        # Queda en la cola de correos; sale cuando hay un servidor de correo saliente configurado.
        plantilla = request.env.ref('autoflow_sitio_web.mail_aviso_solicitud').sudo()
        plantilla.send_mail(lead.id, email_values={'email_to': destino})
