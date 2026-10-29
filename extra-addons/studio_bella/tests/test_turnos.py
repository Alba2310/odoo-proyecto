# -*- coding: utf-8 -*-
from datetime import date, datetime, timedelta

import pytz

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import HttpCase, tagged

from odoo.addons.studio_bella.tests.common import StudioBellaCommon

ASUNCION = pytz.timezone('America/Asuncion')


@tagged('post_install', '-at_install')
class TestTurnosPorInternet(StudioBellaCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.turnos = cls.env['bella.turnos']
        # Peluquería de Paraguay: los celulares se reconocen con o sin el +595.
        cls.company.country_id = cls.env.ref('base.py')
        # La clienta entra a la página el lunes 2 de noviembre a las 8:00: se reserva desde las 9:00.
        cls.ahora = datetime(2026, 11, 2, 11, 0)

    def _local(self, hora, dia=2):
        """Hora de Asunción del mes de noviembre de 2026, en UTC sin zona (como la guarda Odoo)."""
        horas, minutos = map(int, hora.split(':'))
        momento = ASUNCION.localize(datetime(2026, 11, dia, horas, minutos))
        return momento.astimezone(pytz.utc).replace(tzinfo=None)

    def _horas(self, libres, dia):
        horas = [pytz.utc.localize(inicio).astimezone(ASUNCION) for inicio in libres]
        return [hora.strftime('%H:%M') for hora in horas if hora.date() == dia]

    def _reservar(self, hora, servicios=None, telefono='0971 555 019', nombre='Clienta de internet', **valores):
        return self.turnos._reservar(servicios or self.corte, self._local(hora), nombre, telefono,
                                     ahora=self.ahora, **valores)

    # Horarios libres

    def test_horarios_libres_respetan_horario_y_citas(self):
        self._cita()  # Lunes de 10:00 a 11:00.
        libres = self.turnos._disponibilidad(self.corte, ahora=self.ahora)
        lunes = self._horas(libres, date(2026, 11, 2))
        # 8:00 y 8:30 quedan dentro de la hora de anticipación; 9:30 y 10:30 chocan con la cita.
        self.assertEqual(lunes[:3], ['09:00', '11:00', '11:30'])
        self.assertNotIn('09:30', lunes)
        self.assertNotIn('10:30', lunes)
        self.assertEqual(lunes[-1], '18:00')  # Termina justo a las 19:00, cuando cierra.
        self.assertFalse(self._horas(libres, date(2026, 11, 8)))  # Domingo: cerrado.
        self.assertEqual(self._horas(libres, date(2026, 11, 3))[0], '08:00')

        dias = self.turnos._dias(self.corte, ahora=self.ahora)
        self.assertEqual(len(dias), 14)
        self.assertEqual(dias[0]['fecha'], '2026-11-02')
        self.assertEqual(dias[0]['horarios'][0]['hora'], '09:00')
        self.assertFalse(dias[6]['horarios'])  # Domingo 8.

    def test_un_servicio_largo_puede_pasar_del_mediodia(self):
        lunes = self._horas(self.turnos._disponibilidad(self.color, ahora=self.ahora), date(2026, 11, 2))
        self.assertIn('11:00', lunes)  # De 11:00 a 12:30: la mañana y la tarde son seguidas.
        self.assertEqual(lunes[-1], '17:30')

    def test_feriado_sin_horarios(self):
        self.env['resource.calendar.leaves'].create({
            'name': 'Feriado de prueba',
            'calendar_id': self.horario.id,
            'date_from': self._local('00:00', dia=3),
            'date_to': self._local('23:59', dia=3),
        })
        libres = self.turnos._disponibilidad(self.corte, ahora=self.ahora)
        self.assertFalse(self._horas(libres, date(2026, 11, 3)))
        self.assertTrue(self._horas(libres, date(2026, 11, 4)))

    def test_solo_servicios_y_estilistas_habilitados(self):
        self.assertIn(self.corte, self.turnos._servicios())
        self.assertNotIn(self.estilista, self.turnos._estilistas(self.manicura))
        self.assertFalse(self.turnos._disponibilidad(self.manicura, ahora=self.ahora))

        self.corte.bella_reserva_online = False
        self.assertNotIn(self.corte, self.turnos._servicios())
        with self.assertRaises(UserError):
            self._reservar('11:00')

    # Reserva

    def test_reservar_agenda_la_cita_y_reconoce_a_la_clienta(self):
        cita = self._reservar('11:00', nombre='Clienta Nueva', email='nueva@example.com', nota='Tengo el pelo largo')
        self.assertEqual(cita.origen, 'internet')
        self.assertEqual(cita.estado, 'agendada')
        self.assertEqual(cita.estilista_id, self.estilista)
        self.assertEqual(cita.fecha_inicio, self._local('11:00'))
        self.assertEqual(cita.servicio_ids.servicio_id, self.corte)
        self.assertEqual(cita.nota, 'Tengo el pelo largo')
        cliente = cita.cliente_id
        self.assertEqual((cliente.name, cliente.phone, cliente.email),
                         ('Clienta Nueva', '0971 555 019', 'nueva@example.com'))

        # El mismo celular escrito de otra forma: es la misma clienta.
        otra = self._reservar('14:00', telefono='+595 971 555019', nombre='Clienta')
        self.assertEqual(otra.cliente_id, cliente)
        self.assertTrue(any('Nombre que escribió: Clienta' in mensaje.body for mensaje in otra.message_ids))

        # Ese horario ya no está libre.
        with self.assertRaisesRegex(UserError, 'ya no está libre'):
            self._reservar('11:00', telefono='0981 222 333')

        confirmacion = self.turnos._confirmacion(cita, 'Clienta Nueva')
        self.assertEqual(confirmacion['nombre'], 'Clienta')
        self.assertIn('11:00', confirmacion['turno'])

    def test_reservar_revisa_los_datos(self):
        with self.assertRaisesRegex(UserError, 'nombre'):
            self._reservar('11:00', nombre='  ')
        with self.assertRaisesRegex(UserError, 'celular'):
            self._reservar('11:00', telefono='123')
        with self.assertRaisesRegex(UserError, 'correo'):
            self._reservar('11:00', email='sin-arroba')
        with self.assertRaisesRegex(UserError, 'no está libre'):
            self._reservar('08:30')  # Falta menos de una hora.
        with self.assertRaisesRegex(UserError, 'no está libre'):
            self.turnos._reservar(self.corte, self._local('10:00', dia=8), 'Clienta', '0971 555 019',
                                  ahora=self.ahora)  # Domingo.
        with self.assertRaisesRegex(UserError, 'servicio'):
            self.turnos._reservar(self.env['product.product'], self._local('11:00'), 'Clienta', '0971 555 019',
                                  ahora=self.ahora)

    def test_maximo_de_turnos_pendientes_por_clienta(self):
        for hora in ('09:00', '11:00', '12:00'):
            self._reservar(hora)
        with self.assertRaisesRegex(UserError, 'Ya tenés 3 turnos'):
            self._reservar('15:00')

    def test_cualquiera_le_da_el_turno_a_la_estilista_mas_libre(self):
        otra = self.env['hr.employee'].create({
            'name': 'Otra estilista de prueba',
            'bella_estilista': True,
            'resource_calendar_id': self.horario.id,
            'tz': 'America/Asuncion',
        })
        self._cita()  # La primera estilista ya tiene un turno el lunes a las 10:00.
        self.assertEqual(self._reservar('15:00').estilista_id, otra)
        self.assertEqual(self._reservar('10:00', telefono='0981 222 333').estilista_id, otra)
        # Con una estilista elegida, solo cuentan sus horarios.
        with self.assertRaisesRegex(UserError, 'no está libre'):
            self._reservar('10:00', telefono='0981 444 555', estilista=self.estilista)

    def test_servicios_de_distintas_estilistas_uno_detras_del_otro(self):
        manicurista = self.env['hr.employee'].create({
            'name': 'Manicurista de prueba',
            'bella_estilista': True,
            'resource_calendar_id': self.horario.id,
            'tz': 'America/Asuncion',
            'bella_servicio_ids': [Command.set(self.manicura.ids)],
        })
        corte_y_manicura = self.corte | self.manicura  # Nadie hace las dos cosas.
        self.assertEqual(self.turnos._tramos(corte_y_manicura), [self.corte, self.manicura])
        self.assertEqual(self.turnos._tramos(self.manicura | self.corte), [self.manicura, self.corte])

        # La manicurista ya tiene un turno de 10:00 a 10:45.
        self._cita(inicio=self._local('10:00'), servicios=self.manicura, estilista_id=manicurista.id)
        # Corte (1 h) y después manicura: a las 9:00 y 9:30 la manicura chocaría con ese turno.
        lunes = self._horas(self.turnos._disponibilidad(corte_y_manicura, ahora=self.ahora), date(2026, 11, 2))
        self.assertEqual(lunes[0], '10:00')
        # Manicura (45 min) y después corte: el corte empieza a las 9:45, fuera de los horarios redondos.
        manicura_y_corte = self.manicura | self.corte
        lunes = self._horas(self.turnos._disponibilidad(manicura_y_corte, ahora=self.ahora), date(2026, 11, 2))
        self.assertEqual(lunes[0], '09:00')
        # Con una estilista elegida, tiene que hacer todo ella.
        self.assertFalse(self.turnos._disponibilidad(corte_y_manicura, estilista=self.estilista, ahora=self.ahora))

        citas = self._reservar('09:00', servicios=manicura_y_corte, nombre='Clienta Combinada')
        self.assertEqual(len(citas), 2)
        self.assertEqual(citas.mapped('estilista_id'), manicurista | self.estilista)
        self.assertEqual([cita.fecha_inicio for cita in citas], [self._local('09:00'), self._local('09:45')])
        self.assertEqual(citas.cliente_id.name, 'Clienta Combinada')
        self.assertTrue(all('varios servicios seguidos' in cita.message_ids[0].body for cita in citas))

        confirmacion = self.turnos._confirmacion(citas, 'Clienta Combinada')
        self.assertIn('Manicurista de prueba', confirmacion['estilista'])
        self.assertIn('Estilista de prueba', confirmacion['estilista'])
        self.assertEqual(confirmacion['servicios'], 'Manicura de prueba + Corte de prueba')


@tagged('post_install', '-at_install')
class TestPaginaTurnos(HttpCase):
    """La página pública funciona sin iniciar sesión."""

    def test_pagina_y_horarios(self):
        categoria = self.env.ref('studio_bella.categoria_servicios')
        servicio = self.env['product.product'].create({
            'name': 'Servicio de la página', 'type': 'service', 'list_price': 70, 'bella_duracion': 30,
            'categ_id': categoria.id,
        })
        horario = self.env.ref('studio_bella.horario_studio_bella')
        estilista = self.env['hr.employee'].create({
            'name': 'Estilista de la página', 'bella_estilista': True, 'resource_calendar_id': horario.id,
            'bella_servicio_ids': [Command.set(servicio.ids)],
        })

        respuesta = self.url_open('/turnos')
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('Reservá tu turno', respuesta.text)
        self.assertIn('Servicio de la página', respuesta.text)

        dias = self.make_jsonrpc_request('/turnos/horarios', {'servicio_ids': [servicio.id], 'estilista_id': estilista.id})
        self.assertEqual(len(dias), 14)
        self.assertTrue(any(dia['horarios'] for dia in dias))

        robot = self.make_jsonrpc_request('/turnos/reservar', {
            'servicio_ids': [servicio.id], 'inicio': '2030-01-07 12:00:00', 'nombre': 'Robot',
            'telefono': '0981 000 000', 'web': 'http://spam.example.com',
        })
        self.assertIn('error', robot)
