# -*- coding: utf-8 -*-
from datetime import datetime, time, timedelta
from urllib.parse import unquote

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.studio_bella.tests.common import StudioBellaCommon


@tagged('post_install', '-at_install')
class TestClientasQueNoVuelven(StudioBellaCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company.country_id = cls.env.ref('base.py')
        cls.company.bella_url_turnos = 'https://turnos.example.com/turnos'
        cls.hoy = fields.Date.context_today(cls.env.user)
        # Lunes de hace 10 semanas y lunes de la semana que viene, a las 10:00 de Asunción (13:00 UTC).
        lunes = cls.hoy - timedelta(days=cls.hoy.weekday())
        cls.hace_10_semanas = datetime.combine(lunes - timedelta(weeks=10), time(13, 0))
        cls.semana_que_viene = datetime.combine(lunes + timedelta(weeks=1), time(13, 0))
        cls.ana = cls.env['res.partner'].create({'name': 'Ana de prueba', 'phone': '0981 111 222'})
        cls.bea = cls.env['res.partner'].create({'name': 'Bea de prueba', 'phone': '0982 333 444'})

    def _cita_de(self, cliente, inicio, **valores):
        return self._cita(inicio=inicio, cliente_id=cliente.id, **valores)

    def test_ultima_visita_cuenta_solo_las_cobradas(self):
        self.assertFalse(self.ana.bella_ultima_visita)
        vieja = self._cita_de(self.ana, self.hace_10_semanas)
        self._cobrar(vieja)
        self._cita_de(self.ana, self.hace_10_semanas + timedelta(days=1), estado='cancelada')

        self.assertEqual(self.ana.bella_ultima_visita, self.hace_10_semanas.date())
        self.assertEqual(self.ana.bella_visitas, 1)
        self.assertEqual(self.ana.bella_total_gastado, 100)
        self.assertEqual(self.ana.bella_dias_sin_venir, (self.hoy - self.hace_10_semanas.date()).days)

    def test_lista_sin_las_que_ya_pidieron_turno(self):
        self._cobrar(self._cita_de(self.ana, self.hace_10_semanas))
        self._cobrar(self._cita_de(self.bea, self.hace_10_semanas + timedelta(hours=2)))
        proxima = self._cita_de(self.bea, self.semana_que_viene)
        self.assertEqual(self.bea.bella_proxima_cita, proxima.fecha_inicio)

        hace_6_semanas = self.hoy - timedelta(weeks=6)
        no_vuelven = self.env['res.partner'].search([
            ('id', 'in', (self.ana | self.bea).ids),
            ('bella_ultima_visita', '<', hace_6_semanas),
            ('bella_proxima_cita', '=', False),
        ])
        self.assertEqual(no_vuelven, self.ana)

        # El próximo turno también se filtra por fecha (filtro personalizado).
        Partner = self.env['res.partner']
        self.assertEqual(Partner.search([('id', 'in', (self.ana | self.bea).ids),
                                         ('bella_proxima_cita', '>', proxima.fecha_inicio - timedelta(days=1))]),
                         self.bea)
        self.assertFalse(Partner.search([('id', '=', self.bea.id),
                                         ('bella_proxima_cita', '<', proxima.fecha_inicio)]))

        # Si Bea cancela el turno, vuelve a la lista.
        proxima.action_cancelar()
        self.assertFalse(self.bea.bella_proxima_cita)
        self.assertIn(self.bea, self.env['res.partner'].search([('bella_proxima_cita', '=', False)]))

    def test_invitar_por_whatsapp(self):
        self._cobrar(self._cita_de(self.ana, self.hace_10_semanas))
        accion = self.ana.action_bella_invitar()

        self.assertTrue(accion['url'].startswith('https://wa.me/595981111222?text='))
        texto = unquote(accion['url'].split('text=')[1])
        semanas = (self.hoy - self.hace_10_semanas.date()).days // 7
        self.assertIn(f'Hace {semanas} semanas que no te vemos', texto)
        self.assertIn('https://turnos.example.com/turnos', texto)
        self.assertEqual(self.ana.bella_invitada_el, self.hoy)
        self.assertIn('Invitación a volver', self.ana.message_ids[0].body)

        sin_telefono = self.env['res.partner'].create({'name': 'Sin teléfono'})
        with self.assertRaises(UserError):
            sin_telefono.action_bella_invitar()
