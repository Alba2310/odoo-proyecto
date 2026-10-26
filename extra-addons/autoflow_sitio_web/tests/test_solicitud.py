# -*- coding: utf-8 -*-
from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestSolicitudSitioWeb(HttpCase):

    def setUp(self):
        super().setUp()
        # Con varias bases en el servidor, la sesión le indica a Odoo en cuál probar.
        # En producción la instancia "ventas" atiende una sola base, así que el sitio no necesita sesión.
        self.authenticate(None, None)
        self.env['ir.config_parameter'].sudo().set_param('autoflow_sitio_web.email_aviso', 'ventas@example.com')

    def _enviar(self, **cambios):
        datos = {
            'nombre': 'María González',
            'empresa': 'Automotores del Sur',
            'telefono': '0981 123 456',
            'email': 'maria@example.com',
            'tipo': 'ambos',
            'usuarios': '4 a 10',
            'plan': 'profesional',
            'mensaje': 'Queremos avisar a los clientes.',
            **cambios,
        }
        return self.url_open('/autoflow/solicitud', data=datos)

    def _oportunidades(self):
        return self.env['crm.lead'].search([('email_from', '=', 'maria@example.com')])

    def test_crea_oportunidad_y_aviso(self):
        respuesta = self._enviar()

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.json()['ok'])
        self.assertEqual(respuesta.headers.get('Access-Control-Allow-Origin'), '*')

        lead = self._oportunidades()
        self.assertEqual(len(lead), 1)
        self.assertEqual(lead.type, 'opportunity')
        self.assertEqual(lead.contact_name, 'María González')
        self.assertEqual(lead.partner_name, 'Automotores del Sur')
        self.assertIn(self.env.ref('autoflow_sitio_web.tag_sitio_web'), lead.tag_ids)
        self.assertNotEqual(lead.user_id, self.env.ref('base.public_user'))
        self.assertIn('Concesionaria con taller', lead.description)
        self.assertIn('Profesional', lead.description)

        # Un solo correo: el aviso propio, sin la notificación estándar de asignación.
        correos = self.env['mail.mail'].search([('model', '=', 'crm.lead'), ('res_id', '=', lead.id)])
        self.assertEqual(len(correos), 1)
        self.assertEqual(correos.email_to, 'ventas@example.com')
        self.assertIn('Automotores del Sur', correos.subject)

    def test_rechaza_datos_invalidos(self):
        respuesta = self._enviar(email='no-es-un-correo', telefono='12')

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(set(respuesta.json()['errores']), {'email', 'telefono'})
        self.assertFalse(self.env['crm.lead'].search([('partner_name', '=', 'Automotores del Sur')]))

    def test_ignora_robots(self):
        respuesta = self._enviar(sitio_web='http://spam.example.com')

        self.assertTrue(respuesta.json()['ok'])
        self.assertFalse(self._oportunidades())

    def test_texto_del_cliente_no_se_interpreta_como_html(self):
        self._enviar(mensaje='<script>alert(1)</script>')

        self.assertNotIn('<script>', self._oportunidades().description)
