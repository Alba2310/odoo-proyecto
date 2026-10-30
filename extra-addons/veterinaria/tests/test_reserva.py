# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import HttpCase, tagged

from odoo.addons.veterinaria.tests.common import PatitasCommon

# Domingo 1 de noviembre de 2026 a las 9:00 de Asunción: el lunes 2 es el primer día con horarios.
DOMINGO = datetime(2026, 11, 1, 12, 0)


@tagged('post_install', '-at_install')
class TestReserva(PatitasCommon):

    def setUp(self):
        super().setUp()
        self.reserva = self.env['vet.reserva']

    def _datos(self, **valores):
        return {'mascota': 'Pelusa', 'especie_id': self.gato.id, 'nombre': 'Carlos Nuevo',
                'telefono': '0981 555 444', **valores}

    def test_horarios_libres(self):
        dias = self.reserva._dias(self.consulta, self.veterinaria, ahora=DOMINGO)
        self.assertEqual(len(dias), 14)
        self.assertEqual(dias[0]['semana'], 'Hoy')
        self.assertFalse(dias[0]['horarios'])  # el domingo está cerrado
        lunes = [horario['hora'] for horario in dias[1]['horarios']]
        self.assertEqual(lunes[0], '08:00')
        self.assertEqual(lunes[-1], '18:30')
        self.assertEqual(len(lunes), 22)
        # Un turno dado ocupa su horario.
        self._atencion()
        lunes = [horario['hora'] for horario in self.reserva._dias(self.consulta, ahora=DOMINGO)[1]['horarios']]
        self.assertNotIn('10:00', lunes)
        self.assertIn('10:30', lunes)
        # El sábado se atiende hasta las 13:00.
        sabado = [horario['hora'] for horario in self.reserva._dias(self.consulta, ahora=DOMINGO)[6]['horarios']]
        self.assertEqual(sabado[-1], '12:30')

    def test_cada_area_tiene_su_gente(self):
        bano = self.reserva._libres(self.bano, ahora=DOMINGO)
        self.assertEqual(set().union(*(libres.ids for libres in bano.values())), {self.peluquera.id})
        with self.assertRaises(UserError):
            self.reserva._libres(self.consulta | self.bano, ahora=DOMINGO)

    def test_reservar_da_de_alta_al_dueno_y_a_la_mascota(self):
        atencion = self.reserva._reservar(self.antirrabica, self.lunes_10, self._datos(nota='Es miedosa'),
                                          ahora=DOMINGO)
        self.assertEqual(atencion.origen, 'internet')
        self.assertEqual(atencion.estado, 'reservada')
        self.assertEqual(atencion.profesional_id, self.veterinaria)
        self.assertEqual(atencion.motivo, 'Es miedosa')
        self.assertEqual(atencion.mascota_id.name, 'Pelusa')
        self.assertEqual(atencion.mascota_id.especie_id, self.gato)
        self.assertEqual(atencion.dueno_id.name, 'Carlos Nuevo')
        self.assertEqual(atencion.dueno_id.mobile, '0981 555 444')
        confirmacion = self.reserva._confirmacion(atencion, 'Carlos Nuevo')
        self.assertEqual(confirmacion['nombre'], 'Carlos')
        self.assertEqual(confirmacion['mascota'], 'Pelusa')

    def test_reconoce_al_dueno_por_el_celular_y_a_la_mascota_por_el_nombre(self):
        atencion = self.reserva._reservar(self.consulta, self.lunes_10, self._datos(
            mascota='toby', especie_id=self.perro.id, nombre='Ana', telefono='+595 981 000900'), ahora=DOMINGO)
        self.assertEqual(atencion.dueno_id, self.duena)
        self.assertEqual(atencion.mascota_id, self.toby)
        self.assertIn('Nombre que escribió: Ana', atencion.message_ids[0].body)

    def test_lo_que_no_se_puede_reservar(self):
        self._atencion()
        with self.assertRaises(UserError):  # ya está ocupado
            self.reserva._reservar(self.consulta, self.lunes_10, self._datos(), ahora=DOMINGO)
        with self.assertRaises(UserError):  # el baño es solo para perros
            self.reserva._reservar(self.bano, self.lunes_10, self._datos(), ahora=DOMINGO)
        with self.assertRaises(UserError):  # sin celular
            self.reserva._reservar(self.antirrabica, self.lunes_10 + timedelta(hours=2), self._datos(telefono='123'),
                                   ahora=DOMINGO)
        with self.assertRaises(UserError):  # sin especie
            self.reserva._reservar(self.antirrabica, self.lunes_10 + timedelta(hours=2),
                                   self._datos(especie_id=False), ahora=DOMINGO)

    def test_hasta_tres_turnos_pendientes(self):
        for hora in range(3):
            self.reserva._reservar(self.antirrabica, self.lunes_10 + timedelta(hours=hora), self._datos(),
                                   ahora=DOMINGO)
        with self.assertRaises(UserError):
            self.reserva._reservar(self.antirrabica, self.lunes_10 + timedelta(hours=4), self._datos(),
                                   ahora=DOMINGO)
        # La misma mascota no se repite.
        self.assertEqual(len(self.env['vet.mascota'].search([('name', '=', 'Pelusa')])), 1)

    def test_datos_de_la_pagina(self):
        datos = self.reserva._datos_pagina()
        servicios = {servicio['id']: servicio for servicio in datos['servicios']}
        self.assertIn(self.consulta.id, servicios)
        self.assertEqual(servicios[self.bano.id]['especies'], self.perro.ids)
        self.assertFalse(servicios[self.antirrabica.id]['es_servicio'])
        self.assertNotIn(self.alimento.id, servicios)
        self.assertIn('🐶', [especie['emoji'] for especie in datos['especies']])


@tagged('post_install', '-at_install')
class TestPaginaReserva(HttpCase):
    """La página pública funciona sin iniciar sesión."""

    def test_pagina_horarios_y_robots(self):
        servicio = self.env['product.product'].create({
            'name': 'Consulta de la página', 'type': 'service', 'list_price': 70, 'vet_area': 'consultorio',
            'vet_duracion': 30, 'vet_reserva_online': True,
        })
        horario = self.env.ref('veterinaria.horario_patitas')
        profesional = self.env['hr.employee'].create({
            'name': 'Veterinario de la página', 'vet_atiende': 'consultorio', 'resource_calendar_id': horario.id,
            'vet_servicio_ids': [Command.set(servicio.ids)],
        })

        respuesta = self.url_open('/reservar')
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('Turnos por internet', respuesta.text)
        self.assertIn('Consulta de la página', respuesta.text)

        dias = self.make_jsonrpc_request('/reservar/horarios', {'servicio_ids': [servicio.id],
                                                                'profesional_id': profesional.id})
        self.assertEqual(len(dias), 14)
        self.assertTrue(any(dia['horarios'] for dia in dias))

        robot = self.make_jsonrpc_request('/reservar/confirmar', {
            'servicio_ids': [servicio.id], 'inicio': '2030-01-07 12:00:00', 'web': 'http://spam.example.com',
            'datos': {'mascota': 'Robot', 'nombre': 'Robot', 'telefono': '0981 000 000'},
        })
        self.assertIn('error', robot)
        self.assertFalse(self.env['vet.mascota'].search([('name', '=', 'Robot')]))
