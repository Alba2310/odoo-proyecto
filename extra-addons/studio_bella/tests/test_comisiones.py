# -*- coding: utf-8 -*-
from datetime import date, timedelta

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import new_test_user, tagged

from odoo.addons.studio_bella.tests.common import StudioBellaCommon


@tagged('post_install', '-at_install')
class TestComisiones(StudioBellaCommon):
    """La liquidación cuenta el día del cobro (la fecha de la factura), no el del turno."""

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
        corte._bella_cobrar('efectivo', fecha=date(2026, 11, 2))  # Corte 100 + shampoo 50
        color._bella_cobrar('tarjeta', fecha=date(2026, 11, 2))  # Color 200
        return corte, color

    def test_calcula_la_comision_del_periodo(self):
        corte, color = self._citas_de_noviembre()
        # No entran: una cita sin cobrar, la de otra estilista y una cobrada en diciembre.
        self._cita(inicio=self.lunes_10 + timedelta(days=1))
        self._cita(inicio=self.lunes_10 + timedelta(days=2), estilista_id=self.otra_estilista.id)._bella_cobrar(
            'efectivo', fecha=date(2026, 11, 4))
        self._cita(inicio=self.lunes_10 + timedelta(weeks=4, days=1))._bella_cobrar(
            'efectivo', fecha=date(2026, 12, 1))

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

    def test_cuenta_el_dia_del_cobro(self):
        # Turno del sábado 31/10, cobrado el lunes 2/11 (por ejemplo, después de pagar las comisiones de octubre).
        cita = self._cita(inicio=self.lunes_10 - timedelta(days=2))
        cita._bella_cobrar('efectivo', fecha=date(2026, 11, 2))
        octubre = self._liquidacion(fecha_desde=date(2026, 10, 1), fecha_hasta=date(2026, 10, 31))
        self.assertFalse(octubre.servicio_ids)
        self.assertEqual(self._liquidacion().servicio_ids, cita.servicio_ids)

    def test_factura_anulada_no_cuenta(self):
        corte, color = self._citas_de_noviembre()
        nota = corte.factura_id._reverse_moves([{'invoice_date': date(2026, 11, 3)}])
        nota.action_post()
        liquidacion = self._liquidacion()
        self.assertEqual(liquidacion.servicio_ids, color.servicio_ids)
        self.assertFalse(liquidacion.producto_ids)

    def test_nada_se_paga_dos_veces(self):
        self._citas_de_noviembre()
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
        nueva._bella_cobrar('efectivo', fecha=date(2026, 11, 5))
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
        # Tampoco se le pueden sacar servicios por fuera de la pantalla.
        with self.assertRaises(UserError):
            liquidacion.servicio_ids[0].liquidacion_id = False

        # Vuelta a borrador se puede borrar, y sus servicios quedan libres para otra liquidación.
        servicios = liquidacion.servicio_ids
        liquidacion.action_borrador()
        liquidacion.unlink()
        self.assertFalse(servicios.liquidacion_id)
        self.assertEqual(self._liquidacion().servicio_ids, servicios)

    def test_las_lineas_cobradas_no_se_cambian(self):
        corte, _color = self._citas_de_noviembre()
        with self.assertRaises(UserError):
            corte.servicio_ids.precio = 1
        with self.assertRaises(UserError):
            corte.producto_ids.unlink()

        # La recepción no puede sacar ni mover líneas de una liquidación.
        recepcion = new_test_user(
            self.env, login='recepcion_comisiones', groups='studio_bella.group_bella_recepcion',
            company_id=self.company.id, company_ids=[Command.set(self.company.ids)],
        )
        with self.assertRaises(AccessError):
            corte.servicio_ids.with_user(recepcion).write({'liquidacion_id': False})

        # Mientras no está cobrada, la cita se corrige libremente.
        abierta = self._cita(inicio=self.lunes_10 + timedelta(days=1))
        abierta.servicio_ids.precio = 90
        self.assertEqual(abierta.total, 90)

    def test_adelantos_mayores_que_la_comision(self):
        self._citas_de_noviembre()
        liquidacion = self._liquidacion(adelantos=1000)
        with self.assertRaises(UserError):
            liquidacion.action_pagar()

    def test_periodo_al_reves(self):
        with self.assertRaises(ValidationError):
            self._liquidacion(fecha_desde=date(2026, 11, 30), fecha_hasta=date(2026, 11, 1))
