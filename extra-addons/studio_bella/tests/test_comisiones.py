# -*- coding: utf-8 -*-
from datetime import date, timedelta

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.studio_bella.tests.common import StudioBellaCommon


@tagged('post_install', '-at_install')
class TestComisiones(StudioBellaCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.estilista.write({'bella_comision_servicios': 40, 'bella_comision_productos': 10})
        cls.otra_estilista = cls.estilista.copy({'name': 'Otra estilista de prueba'})

    def _liquidacion(self, estilista=None, **valores):
        return self.env['bella.liquidacion.comision'].create({
            'estilista_id': (estilista or self.estilista).id,
            'fecha_desde': date(2026, 11, 1),
            'fecha_hasta': date(2026, 11, 30),
            **valores,
        })

    def _citas_de_noviembre(self):
        corte = self._cita(producto_ids=[Command.create({'producto_id': self.shampoo.id, 'cantidad': 1})])
        color = self._cita(inicio=self.lunes_10 + timedelta(hours=2), servicios=self.color)
        self._cobrar(corte)  # Corte 100 + shampoo 50
        self._cobrar(color)  # Color 200
        return corte, color

    def test_calcula_la_comision_del_periodo(self):
        corte, color = self._citas_de_noviembre()
        # No entran: una cita sin cobrar, la de otra estilista y una de diciembre.
        self._cita(inicio=self.lunes_10 + timedelta(days=1))
        self._cobrar(self._cita(inicio=self.lunes_10 + timedelta(days=2), estilista_id=self.otra_estilista.id))
        self._cobrar(self._cita(inicio=self.lunes_10 + timedelta(weeks=4, days=1)))  # Martes 1/12

        liquidacion = self._liquidacion(adelantos=20)
        self.assertEqual(liquidacion.name, 'Estilista de prueba · 01/11 al 30/11/2026')
        self.assertEqual(liquidacion.servicio_ids, corte.servicio_ids | color.servicio_ids)
        self.assertEqual(liquidacion.producto_ids, corte.producto_ids)
        self.assertEqual((liquidacion.porcentaje_servicios, liquidacion.porcentaje_productos), (40, 10))
        self.assertEqual((liquidacion.base_servicios, liquidacion.comision_servicios), (300, 120))
        self.assertEqual((liquidacion.base_productos, liquidacion.comision_productos), (50, 5))
        self.assertEqual(liquidacion.total, 105)  # 120 + 5 - 20 de adelanto

        # El porcentaje se puede ajustar en el borrador.
        liquidacion.porcentaje_servicios = 50
        self.assertEqual(liquidacion.total, 135)

    def test_nada_se_paga_dos_veces(self):
        corte, color = self._citas_de_noviembre()
        primera = self._liquidacion()
        primera.action_pagar()
        self.assertEqual(primera.estado, 'pagada')
        self.assertTrue(primera.fecha_pago)

        segunda = self._liquidacion()
        self.assertFalse(segunda.servicio_ids)
        with self.assertRaises(UserError):
            segunda.action_pagar()

        # Una cita cobrada después entra en la liquidación en borrador al actualizarla.
        nueva = self._cita(inicio=self.lunes_10 + timedelta(days=3))
        self._cobrar(nueva)
        segunda.action_actualizar()
        self.assertEqual(segunda.servicio_ids, nueva.servicio_ids)

    def test_pagada_no_se_cambia_ni_se_borra(self):
        self._citas_de_noviembre()
        liquidacion = self._liquidacion()
        liquidacion.action_pagar()
        with self.assertRaises(UserError):
            liquidacion.adelantos = 50
        with self.assertRaises(UserError):
            liquidacion.unlink()

        # Vuelta a borrador se puede borrar, y sus servicios quedan libres para otra liquidación.
        servicios = liquidacion.servicio_ids
        liquidacion.action_borrador()
        liquidacion.unlink()
        self.assertFalse(servicios.liquidacion_id)
        self.assertEqual(self._liquidacion().servicio_ids, servicios)

    def test_adelantos_mayores_que_la_comision(self):
        self._citas_de_noviembre()
        liquidacion = self._liquidacion(adelantos=1000)
        with self.assertRaises(UserError):
            liquidacion.action_pagar()

    def test_periodo_al_reves(self):
        with self.assertRaises(ValidationError):
            self._liquidacion(fecha_desde=date(2026, 11, 30), fecha_hasta=date(2026, 11, 1))
