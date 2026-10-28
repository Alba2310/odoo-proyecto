# -*- coding: utf-8 -*-
import re
from datetime import timedelta
from urllib.parse import unquote

from dateutil.relativedelta import relativedelta

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import Form, HttpCase, tagged

from odoo.addons.alquileres.tests.test_alquileres import AlquileresCommon


@tagged('post_install', '-at_install')
class TestOga(AlquileresCommon):
    """Gastos y ganancia, cargos extra, mantenimiento, actas, depósito, reajuste, renovación y puntaje."""

    def _activo(self, **valores):
        contrato = self._contrato(**valores)
        contrato.action_activar()
        return contrato

    def _vencidas(self, contrato):
        return contrato.cuota_ids.filtered('atrasada').sorted('fecha_vencimiento')

    def test_cargos_extra_en_la_cuota(self):
        contrato = self._activo()
        cuota = self._vencidas(contrato)[0]
        cuota.cargo_ids = [Command.create({'concepto': 'agua', 'detalle': 'Agua de agosto', 'monto': 85000})]
        self.assertEqual((cuota.cargos, cuota.total, cuota.saldo), (85000, 1585000, 1585000))
        self.assertIn('Gs. 1.585.000 (alquiler Gs. 1.500.000 + Agua de agosto Gs. 85.000)', cuota._texto_whatsapp())
        pago = self._pagar(cuota)
        self.assertEqual(cuota.estado, 'pagada')
        self.assertIn('Agua de agosto', pago._detalle_cuota())

    def test_gastos_y_ganancia(self):
        contrato = self._activo()
        self._pagar(self._vencidas(contrato)[0])
        self.env['alquiler.gasto'].create({
            'name': 'Pintura', 'propiedad_id': self.edificio.id, 'unidad_id': self.depto1.id, 'monto': 400000,
        })
        self.env.flush_all()
        movimientos = self.env['alquiler.resultado'].search([('propiedad_id', '=', self.edificio.id)])
        self.assertEqual(sum(movimientos.mapped('ingreso')), 1500000)
        self.assertEqual(sum(movimientos.mapped('gasto')), 400000)
        self.assertEqual(sum(movimientos.mapped('ganancia')), 1100000)

        datos = self.env['alquiler.panel'].datos()
        self.assertEqual([i['clave'] for i in datos['indicadores']], ['cobrado', 'deuda', 'ocupacion', 'ganancia'])
        fila = next(f for f in datos['propiedades'] if f['id'] == self.edificio.id)
        self.assertEqual(fila['ganancia'], 'Gs. 1.100.000')
        self.assertTrue(any('aviso' in pendiente['texto'] for pendiente in datos['atender']))

    def test_mantenimiento_lo_paga_el_dueno(self):
        pedido = self.env['alquiler.mantenimiento'].create({
            'name': 'Cambiar la cerradura', 'unidad_id': self.depto2.id, 'costo': 250000, 'responsable': 'Cerrajero',
        })
        pedido.action_resolver()
        self.assertEqual(pedido.estado, 'resuelto')
        self.assertEqual((pedido.gasto_id.monto, pedido.gasto_id.propiedad_id), (250000, self.edificio))
        with self.assertRaises(UserError):
            pedido.action_resolver()

    def test_mantenimiento_lo_paga_el_inquilino(self):
        contrato = self._activo()
        pedido = self.env['alquiler.mantenimiento'].create({
            'name': 'Vidrio roto', 'unidad_id': self.depto1.id, 'costo': 120000, 'paga': 'inquilino',
        })
        self.assertEqual(pedido.inquilino_id, self.inquilino)
        pedido.action_resolver()
        self.assertEqual(pedido.cargo_id.cuota_id, contrato._cuota_para_cargos())
        self.assertEqual(pedido.cargo_id.cuota_id.cargos, 120000)
        sin_contrato = self.env['alquiler.mantenimiento'].create({
            'name': 'Canilla', 'unidad_id': self.depto2.id, 'costo': 50000, 'paga': 'inquilino',
        })
        with self.assertRaises(UserError):
            sin_contrato.action_resolver()

    def test_acta_de_entrega(self):
        contrato = self._activo()
        with Form(self.env['alquiler.acta']) as formulario:
            formulario.contrato_id = contrato
            formulario.lectura_ande = '12345'
        acta = formulario.record
        self.assertEqual(len(acta.linea_ids), 10)
        self.assertEqual(acta.name, 'Acta de entrada · Edificio de prueba · Depto 1')
        html = self.env['ir.actions.report']._render_qweb_html('alquileres.report_acta', acta.ids)[0].decode()
        self.assertIn('Paredes y pintura', html)
        self.assertIn('12345', html)

    def test_terminar_con_el_deposito(self):
        # Vence el día de ayer de cada mes: ninguna cuota vence hoy, así la deuda es solo lo atrasado.
        contrato = self._activo(deposito=2000000, dia_pago=(self.hoy - timedelta(days=1)).day)
        deuda = sum(self._vencidas(contrato).mapped('saldo'))
        for cuota in self._vencidas(contrato)[:-1]:
            self._pagar(cuota)
        # Debe solo la última cuota vencida (1.500.000): el depósito la paga y quedan 500.000.
        asistente = self.env['alquiler.terminar.wizard'].with_context(default_contrato_id=contrato.id).create({
            'descuento': 300000, 'motivo': 'Pared manchada',
        })
        self.assertEqual((asistente.deuda, asistente.a_devolver), (1500000, 200000))
        asistente.action_confirmar()
        self.assertEqual(contrato.estado, 'terminado')
        self.assertEqual((contrato.deposito_aplicado, contrato.deposito_descuento, contrato.deposito_a_devolver),
                         (1500000, 300000, 200000))
        self.assertFalse(contrato.cuota_ids.filtered(lambda c: c.estado != 'pagada'))
        self.assertIn('deposito', contrato.pago_ids.mapped('medio'))
        self.assertGreater(deuda, 0)
        # El depósito no es plata nueva: no cuenta como cobrado en la ganancia.
        self.env.flush_all()
        cobrado = sum(self.env['alquiler.resultado'].search([('propiedad_id', '=', self.edificio.id)]).mapped('ingreso'))
        self.assertEqual(cobrado, sum(contrato.pago_ids.filtered(lambda p: p.medio != 'deposito').mapped('monto')))

    def test_reajuste_anual(self):
        inicio = self.hoy - relativedelta(years=1, days=5)
        contrato = self._activo(fecha_inicio=inicio, dia_pago=inicio.day, reajuste_pct=10)
        self.assertEqual(contrato.fecha_reajuste, inicio + relativedelta(years=1))
        self.assertEqual(contrato.monto_reajustado, 1650000)
        cuotas = contrato.cuota_ids.sorted('fecha_vencimiento')
        self.assertEqual((cuotas[0].monto, cuotas[-1].monto), (1500000, 1650000))
        contrato._aplicar_reajustes()
        self.assertEqual((contrato.monto, contrato.fecha_reajuste), (1650000, inicio + relativedelta(years=2)))
        self.assertTrue(contrato.message_ids.filtered(lambda m: 'Reajuste anual del 10 %' in m.body))

    def test_avisos_del_contrato_y_renovacion(self):
        contrato = self._activo(fecha_fin=self.hoy + timedelta(days=30), reajuste_pct=10)
        contrato.fecha_reajuste = self.hoy + timedelta(days=20)
        self.assertTrue(contrato.vence_pronto and contrato.reajuste_pronto)
        self.assertIn('tu contrato de alquiler de Edificio de prueba · Depto 1 vence el',
                      unquote(contrato.action_avisar_vencimiento()['url']))
        self.assertIn('pasa de Gs. 1.500.000 a Gs. 1.650.000', unquote(contrato.action_avisar_reajuste()['url']))

        asistente = self.env['alquiler.renovar.wizard'].with_context(default_contrato_id=contrato.id).create({})
        self.assertEqual((asistente.fecha_fin, asistente.monto), (self.hoy + timedelta(days=30) + relativedelta(years=1),
                                                                  1650000))
        asistente.action_confirmar()
        self.assertEqual((contrato.fecha_fin, contrato.monto), (asistente.fecha_fin, 1650000))
        self.assertEqual(contrato.fecha_reajuste, self.hoy + timedelta(days=31) + relativedelta(years=1))
        self.assertFalse(contrato.vence_pronto)

    def test_puntaje_del_inquilino(self):
        contrato = self._activo(fecha_inicio=self.hoy - timedelta(days=100))
        vencidas = self._vencidas(contrato)
        self._pagar(vencidas[0], fecha=vencidas[0].fecha_vencimiento)
        self._pagar(vencidas[1], fecha=vencidas[1].fecha_vencimiento + timedelta(days=10))
        self.assertEqual(contrato.puntaje, '1')
        self.assertTrue(contrato.puntaje_texto.startswith(f'1 de {len(vencidas)} cuotas a tiempo'))
        self.assertEqual(self.inquilino.alquiler_puntaje, '1')
        nuevo = self._contrato(unidad_id=self.depto2.id)
        self.assertEqual(nuevo.puntaje, '0')

    def test_contrato_impreso(self):
        garante = self.env['res.partner'].create({'name': 'Garante de prueba'})
        contrato = self._activo(garante_id=garante.id, deposito=1500000, reajuste_pct=8,
                                clausulas_extra='Se permite una mascota.')
        html = self.env['ir.actions.report']._render_qweb_html('alquileres.report_contrato', contrato.ids)[0].decode()
        self.assertIn('PRIMERA – OBJETO', html)
        self.assertIn('un millón quinientos mil guaraníes', html)
        self.assertIn('Garante de prueba se constituye en garante solidario', html)
        self.assertIn('Se permite una mascota.', html)

    def test_interesado(self):
        interesado = self.env['alquiler.interesado'].create({
            'name': 'Sofía Martínez', 'telefono': '0981 222 333', 'unidad_id': self.depto2.id,
        })
        url = unquote(interesado.action_whatsapp()['url'])
        self.assertTrue(url.startswith('https://wa.me/595981222333?text=¡Hola Sofía!'))
        self.assertEqual(interesado.estado, 'contactado')


@tagged('post_install', '-at_install')
class TestPaginaSeAlquila(HttpCase):

    def test_pagina_y_consulta(self):
        edificio = self.env['alquiler.propiedad'].create({
            'name': 'Edificio de la página', 'tipo': 'edificio', 'ciudad': 'Luque',
            'unidad_ids': [Command.create({'name': 'Depto 9', 'alquiler_sugerido': 1200000, 'dormitorios': 2}),
                           Command.create({'name': 'Depto 10', 'publicar': False})],
        })
        visible, oculta = edificio.unidad_ids
        respuesta = self.url_open('/se-alquila')
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('Edificio de la página · Depto 9', respuesta.text)
        self.assertIn('Gs. 1.200.000', respuesta.text)
        self.assertNotIn('Depto 10', respuesta.text)

        token = re.search(r'name="csrf_token" value="([^"]+)"', respuesta.text).group(1)
        respuesta = self.url_open('/se-alquila/consulta', data={
            'csrf_token': token, 'nombre': 'Visitante de prueba', 'telefono': '0982 444 555',
            'unidad_id': str(visible.id), 'mensaje': 'Somos dos.',
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('Gracias', respuesta.text)
        interesado = self.env['alquiler.interesado'].search([('name', '=', 'Visitante de prueba')])
        self.assertEqual((interesado.unidad_id, interesado.desde_la_pagina), (visible, True))

        # Un robot que completa el campo oculto no deja nada.
        self.url_open('/se-alquila/consulta', data={'csrf_token': token, 'nombre': 'Robot', 'telefono': '1',
                                                     'web': 'http://spam'})
        self.assertFalse(self.env['alquiler.interesado'].search([('name', '=', 'Robot')]))
        self.assertEqual(self.url_open(f'/se-alquila/foto/{oculta.id}').status_code, 404)
