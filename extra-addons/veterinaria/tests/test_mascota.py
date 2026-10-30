# -*- coding: utf-8 -*-
from datetime import date, datetime, timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.veterinaria.tests.common import PatitasCommon


@tagged('post_install', '-at_install')
class TestMascota(PatitasCommon):

    def test_ficha(self):
        self.assertEqual(self.toby.display_name, 'Toby (Ana Dueña)')
        self.assertEqual(self.toby.emoji, '🐶')
        self.assertTrue(self.toby.edad.startswith('4 años'))
        self.assertEqual(self.duena.vet_mascota_count, 1)
        # Se busca por el nombre del dueño.
        self.assertIn(self.toby, self.env['vet.mascota'].search([('display_name', 'ilike', 'Dueña')]))
        with self.assertRaises(ValidationError):
            self.toby.raza_id = self.env.ref('veterinaria.raza_gato_siames')
        with self.assertRaises(ValidationError):
            self.toby.fecha_nacimiento = fields.Date.context_today(self.toby) + timedelta(days=1)
        self.toby.fallecida = True
        self.assertEqual(self.toby.fecha_fallecimiento, fields.Date.context_today(self.toby))

    def test_linea_de_tiempo(self):
        atencion = self._atencion(productos=self.consulta | self.antirrabica, diagnostico='Otitis', peso=10)
        atencion.action_terminar()
        self.env['vet.peso'].create({'mascota_id': self.toby.id, 'fecha': date(2026, 12, 1), 'peso': 10.8})
        self.env['vet.internacion'].create({
            'mascota_id': self.toby.id, 'lugar_id': self.jaula.id, 'ingreso': datetime(2026, 11, 10, 12, 0),
            'motivo': 'Control de la otitis',
        })
        datos = self.env['vet.mascota'].vet_linea_tiempo(self.toby.id)
        tipos = [evento['tipo'] for evento in datos['eventos']]
        self.assertEqual(tipos, ['internacion', 'consulta', 'vacuna', 'nacimiento'])
        consulta = datos['eventos'][1]
        self.assertEqual(consulta['detalle'], 'Otitis')
        self.assertEqual(consulta['modelo'], 'vet.atencion')
        self.assertEqual(consulta['quien'], 'Veterinaria de prueba')
        self.assertIn('Próxima: 2 de noviembre de 2027', datos['eventos'][2]['detalle'])
        self.assertEqual([peso['peso'] for peso in datos['pesos']], [10, 10.8])
        self.assertEqual(self.toby.peso_actual, 10.8)

    def test_tablero(self):
        llego = self.env['vet.atencion'].create({'mascota_id': self.toby.id, 'origen': 'sin_turno',
                                                 'motivo': 'Se lastimó la pata'})
        estadia = self.env['vet.internacion'].create({
            'mascota_id': self.toby.id, 'lugar_id': self.jaula.id,
            'ingreso': fields.Datetime.now() - timedelta(hours=10),
        })
        datos = self.env['vet.tablero'].datos()
        columnas = {columna['clave']: columna for columna in datos['columnas']}
        self.assertEqual([tarjeta['id'] for tarjeta in columnas['en_espera']['tarjetas']], [llego.id])
        tarjeta = columnas['en_espera']['tarjetas'][0]
        self.assertTrue(tarjeta['sin_turno'])
        self.assertEqual(tarjeta['servicios'], 'Se lastimó la pata')
        self.assertEqual(tarjeta['emoji'], '🐶')
        self.assertEqual([e['id'] for e in datos['estadias']], [estadia.id])
        self.assertTrue(datos['estadias'][0]['sin_control'])  # 10 horas sin control (se pide cada 8)
        # Filtrado por área, la de peluquería no lo muestra.
        datos = self.env['vet.tablero'].datos(area='estetica')
        self.assertFalse(next(c for c in datos['columnas'] if c['clave'] == 'en_espera')['tarjetas'])
