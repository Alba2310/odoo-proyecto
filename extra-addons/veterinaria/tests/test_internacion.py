# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from unittest.mock import patch
from urllib.parse import unquote

from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.veterinaria.tests.common import PatitasCommon


@tagged('post_install', '-at_install')
class TestInternacion(PatitasCommon):

    def _estadia(self, **valores):
        return self.env['vet.internacion'].create({
            'mascota_id': self.toby.id, 'lugar_id': self.jaula.id, 'profesional_id': self.veterinaria.id,
            **valores,
        })

    def test_dias_y_cobro(self):
        # Entró el lunes a la noche y sale el jueves a la mañana: lunes, martes y miércoles.
        estadia = self._estadia(ingreso=datetime(2026, 11, 2, 23, 0), motivo='Gastroenteritis', linea_ids=[
            Command.create({'producto_id': self.alimento.id, 'cantidad': 6}),
        ])
        self.assertEqual(estadia.producto_dia_id, self.dia_internacion)
        self.assertEqual(estadia.precio_dia, 150)
        with self.assertRaises(UserError):
            estadia.action_cobrar()  # primero el alta
        with patch.object(fields.Datetime, 'now', return_value=datetime(2026, 11, 5, 12, 0)):
            estadia.action_dar_alta()
        self.assertEqual(estadia.dias_a_cobrar, 3)
        self.assertEqual(estadia.total, 3 * 150 + 6 * 200)
        # Los remedios ya se usaron: aunque falte stock, se cobra igual.
        self._cobrar(estadia, tarjeta=estadia.total)
        self.assertEqual(estadia.estado, 'cobrada')
        self.assertEqual(estadia.factura_id.amount_total, 1650)
        linea_dias = estadia.factura_id.invoice_line_ids.filtered(lambda l: l.product_id == self.dia_internacion)
        self.assertEqual(linea_dias.quantity, 3)
        self.assertIn('del 02/11 al 05/11', linea_dias.name)
        self.assertEqual(self._stock(self.alimento), -1)
        self.assertTrue(any('stock negativo' in mensaje for mensaje in estadia.message_ids.mapped('body')))

    def test_minimo_un_dia_y_el_hotel_cobra_su_precio(self):
        estadia = self._estadia(tipo='hotel', lugar_id=self.canil.id, profesional_id=False,
                                ingreso=datetime(2026, 11, 2, 12, 0))
        self.assertEqual(estadia.producto_dia_id, self.dia_hotel)
        with patch.object(fields.Datetime, 'now', return_value=datetime(2026, 11, 2, 20, 0)):
            estadia.action_dar_alta()
        self.assertEqual(estadia.dias_a_cobrar, 1)
        self.assertEqual(estadia.total, 50)
        # Se puede corregir a mano antes de cobrar.
        estadia.dias_a_cobrar = 2
        self.assertEqual(estadia.total, 100)

    def test_un_lugar_una_mascota(self):
        self._estadia(ingreso=datetime(2026, 11, 2, 12, 0))
        otra = self.env['vet.mascota'].create({'name': 'Luna', 'dueno_id': self.duena.id, 'especie_id': self.perro.id})
        with self.assertRaises(ValidationError):
            self._estadia(mascota_id=otra.id, ingreso=datetime(2026, 11, 3, 12, 0))
        # Un canil del hotel no sirve para internar.
        with self.assertRaises(ValidationError):
            self._estadia(mascota_id=otra.id, lugar_id=self.canil.id)

    def test_reservas_del_hotel(self):
        reserva = self._estadia(tipo='hotel', lugar_id=self.canil.id, estado='reservada', profesional_id=False,
                                ingreso=datetime(2026, 12, 20, 12, 0), salida_prevista=datetime(2026, 12, 27, 12, 0))
        luna = self.env['vet.mascota'].create({'name': 'Luna', 'dueno_id': self.duena.id, 'especie_id': self.perro.id})
        with self.assertRaises(ValidationError):
            self._estadia(mascota_id=luna.id, tipo='hotel', lugar_id=self.canil.id, estado='reservada',
                          ingreso=datetime(2026, 12, 26, 12, 0), salida_prevista=datetime(2026, 12, 30, 12, 0))
        # Después de la otra, sí.
        self._estadia(mascota_id=luna.id, tipo='hotel', lugar_id=self.canil.id, estado='reservada',
                      ingreso=datetime(2026, 12, 27, 12, 0), salida_prevista=datetime(2026, 12, 30, 12, 0))
        self.assertEqual(reserva.dias_a_cobrar, 7)
        texto = unquote(reserva.action_whatsapp()['url'])
        self.assertIn('Te confirmamos la reserva de Toby en el hotel', texto)
        self.assertIn('domingo 20 de diciembre', texto)
        reserva.action_ingresar()
        self.assertEqual(reserva.estado, 'activa')

    def test_controles_peso_y_parte(self):
        estadia = self._estadia(ingreso=datetime(2026, 11, 2, 12, 0))
        texto = unquote(estadia.action_whatsapp()['url'])
        self.assertIn('Toby ya está instalado en Jaula de prueba', texto)
        self.env['vet.control'].create({
            'internacion_id': estadia.id, 'fecha': datetime(2026, 11, 3, 14, 30), 'peso': 11.8,
            'temperatura': 38.6, 'animo': 'bien', 'comio': 'poco', 'medicacion': 'Antibiótico',
        })
        self.assertEqual(self.toby.peso_actual, 11.8)
        self.assertEqual(estadia.ultimo_control, datetime(2026, 11, 3, 14, 30))
        texto = unquote(estadia.action_whatsapp()['url'])
        self.assertIn('Te contamos cómo está Toby (martes 3 a las 11:30): animado, comió poco, temperatura 38,6 °C.',
                      texto)
        self.assertIn('Le dimos: Antibiótico.', texto)
        with patch.object(fields.Datetime, 'now', return_value=datetime(2026, 11, 4, 12, 0)):
            estadia.action_dar_alta()
        self.assertIn('ya puede volver a casa', unquote(estadia.action_whatsapp()['url']))
        with self.assertRaises(ValidationError):
            self.env['vet.control'].create({'internacion_id': estadia.id, 'temperatura': 38})

    def test_lugares_libres_y_ocupados(self):
        estadia = self._estadia()
        self.assertEqual(self.jaula.estado_lugar, 'ocupado')
        self.assertEqual(self.jaula.estadia_id, estadia)
        self.assertEqual(self.jaula.action_abrir_estadia()['res_id'], estadia.id)
        self.assertEqual(self.canil.estado_lugar, 'libre')
        self.assertEqual(self.canil.action_abrir_estadia()['context']['default_tipo'], 'hotel')
        estadia.action_cancelar()
        self.jaula.invalidate_recordset()
        self.assertEqual(self.jaula.estado_lugar, 'libre')
