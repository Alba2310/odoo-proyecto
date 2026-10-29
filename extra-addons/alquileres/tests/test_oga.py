# -*- coding: utf-8 -*-
import re
from datetime import date, timedelta
from urllib.parse import unquote

from dateutil.relativedelta import relativedelta
from freezegun import freeze_time

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import Form, HttpCase, new_test_user, tagged

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
        cuota = pedido.cargo_id.cuota_id
        self.assertEqual(cuota, contrato._cuota_para_cargos())
        self.assertEqual(cuota.cargos, 120000)
        # El arreglo lo paga el dueño y después se lo cobra al inquilino: también es un gasto, así la ganancia cuadra.
        self.assertEqual((pedido.gasto_id.monto, pedido.gasto_id.name),
                         (120000, 'Vidrio roto (se le cobra al inquilino)'))
        self._pagar(cuota)
        self.env.flush_all()
        movimientos = self.env['alquiler.resultado'].search([('unidad_id', '=', self.depto1.id)])
        self.assertEqual(sum(movimientos.mapped('ganancia')), cuota.monto)
        sin_contrato = self.env['alquiler.mantenimiento'].create({
            'name': 'Canilla', 'unidad_id': self.depto2.id, 'costo': 50000, 'paga': 'inquilino',
        })
        with self.assertRaises(UserError):
            sin_contrato.action_resolver()

    def test_el_encargado_resuelve_una_reparacion(self):
        # El encargado solo lee los gastos, pero al resolver una reparación que paga el dueño se carga el gasto.
        encargado = new_test_user(self.env, login='encargado_reparaciones',
                                  groups='base.group_user,alquileres.group_alquiler_encargado')
        pedido = self.env['alquiler.mantenimiento'].with_user(encargado).create({
            'name': 'Cambiar el cuerito', 'unidad_id': self.depto2.id, 'costo': 80000, 'responsable': 'Plomero',
        })
        pedido.action_resolver()
        self.assertEqual(pedido.estado, 'resuelto')
        gasto = pedido.gasto_id
        self.assertEqual((gasto.monto, gasto.propiedad_id, gasto.unidad_id, gasto.company_id),
                         (80000, self.edificio, self.depto2, self.edificio.company_id))

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
        # Paga los días de mañana: el mes de pago termina hoy, así la deuda es solo lo atrasado y de meses enteros.
        contrato = self._activo(deposito=2000000, dia_pago=(self.hoy + timedelta(days=1)).day)
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
        # Lo que se usa del depósito (la deuda y los daños) cuenta como cobrado el día que se usa; lo que se
        # devuelve, no.
        self.env.flush_all()
        movimientos = self.env['alquiler.resultado'].search([('propiedad_id', '=', self.edificio.id)])
        self.assertEqual(sum(movimientos.mapped('ingreso')), sum(contrato.pago_ids.mapped('monto')) + 300000)
        del_deposito = movimientos.filtered(lambda m: 'depósito' in m.concepto)
        self.assertEqual(set(del_deposito.mapped('fecha')), {contrato.fecha_fin})
        self.assertEqual(sum(del_deposito.mapped('ingreso')), 1500000 + 300000)

    def test_reajuste_anual(self):
        # Cumple un año dentro de 5 días: la cuota que vence ese día ya sale con el alquiler reajustado.
        inicio = self.hoy + timedelta(days=5) - relativedelta(years=1)
        contrato = self._activo(fecha_inicio=inicio, dia_pago=inicio.day, reajuste_pct=10)
        reajuste = inicio + relativedelta(years=1)
        self.assertEqual(contrato.fecha_reajuste, reajuste)
        self.assertEqual(contrato.monto_reajustado, 1650000)
        cuotas = contrato.cuota_ids.sorted('fecha_vencimiento')
        self.assertEqual((cuotas[0].monto, cuotas[-1].monto), (1500000, 1650000))
        contrato._aplicar_reajustes()
        self.assertEqual(contrato.monto, 1500000)  # todavía no llegó
        contrato._aplicar_reajustes(reajuste)
        self.assertEqual((contrato.monto, contrato.fecha_reajuste), (1650000, inicio + relativedelta(years=2)))
        self.assertTrue(contrato.message_ids.filtered(lambda m: 'Reajuste anual del 10 %' in m.body))

    def test_contrato_que_empezo_hace_mas_de_un_anio(self):
        # Se carga un contrato que empezó hace dos años y medio, con el alquiler de ahora: los reajustes que ya
        # pasaron están en ese alquiler y el próximo es el aniversario que viene.
        inicio = self.hoy - relativedelta(years=2, months=6)
        proximo = inicio + relativedelta(years=3)
        contrato = self._activo(fecha_inicio=inicio, dia_pago=inicio.day)
        contrato.reajuste_pct = 10  # como scripts/configurar_base.py
        self.assertEqual(contrato.fecha_reajuste, proximo)
        # Si se escribió a mano un reajuste que ya pasó, al activarlo se corre al próximo aniversario.
        otro = self._contrato(unidad_id=self.depto2.id, fecha_inicio=inicio, dia_pago=inicio.day, reajuste_pct=10,
                              fecha_reajuste=inicio + relativedelta(years=1))
        otro.action_activar()
        self.assertEqual(otro.fecha_reajuste, proximo)
        self.assertEqual(set(otro.cuota_ids.mapped('monto')), {1500000})
        self.env['alquiler.contrato']._cron_generar_cuotas()
        self.assertEqual((contrato.monto, otro.monto), (1500000, 1500000))
        self.assertEqual((contrato.fecha_reajuste, otro.fecha_reajuste), (proximo, proximo))

    def test_terminar_con_fecha_futura(self):
        # Avisa que se va dentro de 45 días: hasta ese día sigue viviendo ahí, así que el contrato sigue vigente,
        # se le siguen creando las cuotas y la unidad no aparece como libre.
        contrato = self._activo(deposito=5000000)
        for cuota in contrato.cuota_ids:
            self._pagar(cuota)
        se_va = self.hoy + timedelta(days=45)
        # Las cuotas hasta ese día; la última, por los días que le tocan.
        por_crear = sum(cuota['monto'] for cuota in contrato._cuotas_por_crear(se_va, fin=se_va))
        self.assertTrue(por_crear)
        asistente = self.env['alquiler.terminar.wizard'].with_context(default_contrato_id=contrato.id).create({
            'fecha': se_va, 'descuento': 100000, 'motivo': 'Pared manchada',
        })
        self.assertEqual(asistente.deuda, por_crear)
        asistente.action_confirmar()
        self.assertEqual((contrato.estado, contrato.fecha_fin, contrato.fecha_salida), ('vigente', se_va, se_va))
        self.assertEqual(self.depto1.estado, 'alquilada')
        self.assertFalse(contrato.vence_pronto)
        self.assertEqual(contrato.action_terminar()['context']['default_fecha'], se_va)

        # El día que se va todavía está: el cron crea las cuotas que faltan. (A mediodía, para que la zona horaria
        # no cambie el día.)
        with freeze_time(f'{se_va} 12:00:00'):
            self.env['alquiler.contrato']._cron_generar_cuotas()
        self.assertEqual(contrato.estado, 'vigente')
        self.assertFalse(contrato._cuotas_por_crear(se_va))
        deuda = sum(contrato.cuota_ids.mapped('saldo'))
        self.assertEqual(deuda, por_crear)
        ultima = contrato.cuota_ids.sorted('fecha_vencimiento')[-1]
        self.assertEqual(ultima.fecha_vencimiento + timedelta(days=ultima.dias - 1), se_va)

        # Al día siguiente se termina solo: el depósito paga lo que quedó debiendo y se descuentan los daños.
        with freeze_time(f'{se_va + timedelta(days=1)} 12:00:00'):
            self.env['alquiler.contrato']._cron_generar_cuotas()
        self.assertEqual((contrato.estado, contrato.fecha_fin, self.depto1.estado), ('terminado', se_va, 'libre'))
        self.assertFalse(contrato.cuota_ids.filtered(lambda c: c.estado != 'pagada'))
        self.assertEqual((contrato.deposito_aplicado, contrato.deposito_descuento, contrato.deposito_a_devolver),
                         (deuda, 100000, 5000000 - deuda - 100000))

    def test_mes_parcial_al_renovar_y_al_terminar(self):
        # Empieza el 20 de enero, paga los 5 y vence el 19 de julio: la cuota de julio es por 15 de 31 días.
        contrato = self._activo(fecha_inicio=date(2025, 1, 20), fecha_fin=date(2025, 7, 19))
        julio = contrato.cuota_ids.filtered(lambda c: c.periodo == date(2025, 7, 1))
        self.assertEqual((julio.name, julio.monto), ('Julio 2025 (15 de 31 días)', round(1500000 * 15 / 31)))
        # Renueva desde el 20 de julio con 1.600.000: julio pasa a ser el mes entero (los 16 días que faltaban, con
        # el alquiler nuevo) y ningún día se cobra dos veces.
        asistente = self.env['alquiler.renovar.wizard'].with_context(default_contrato_id=contrato.id).create({
            'monto': 1600000,
        })
        asistente.action_confirmar()
        self.assertEqual((julio.name, julio.monto), ('Julio 2025', round(1500000 * 15 / 31) + round(1600000 * 16 / 31)))
        contrato._generar_cuotas()
        agosto = contrato.cuota_ids.filtered(lambda c: c.periodo == date(2025, 8, 1))
        self.assertEqual((agosto.fecha_vencimiento, agosto.monto), (date(2025, 8, 5), 1600000))
        self.assertEqual(sum(contrato.cuota_ids.mapped('dias')), (date(2026, 7, 20) - date(2025, 1, 20)).days)
        # Se va el 14 de septiembre: esa cuota es del 5 al 14 (10 de 30 días) y las siguientes se borran.
        contrato._terminar(date(2025, 9, 14))
        septiembre = contrato.cuota_ids.sorted('fecha_vencimiento')[-1]
        self.assertEqual((septiembre.name, septiembre.monto), ('Septiembre 2025 (10 de 30 días)',
                                                              round(1600000 * 10 / 30)))
        self.assertEqual(sum(contrato.cuota_ids.mapped('dias')), (date(2025, 9, 15) - date(2025, 1, 20)).days)

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
        # Las cuotas que faltan del plazo actual siguen con el alquiler de ahora; el nuevo, desde la renovación.
        inicio = self.hoy + timedelta(days=31)
        self.assertEqual((contrato.fecha_fin, contrato.monto), (asistente.fecha_fin, 1500000))
        self.assertEqual((contrato.monto_renovacion, contrato.fecha_renovacion), (1650000, inicio))
        self.assertEqual((contrato._monto_para(inicio - timedelta(days=1)), contrato._monto_para(inicio)),
                         (1500000, 1650000))
        self.assertEqual(contrato.fecha_reajuste, inicio + relativedelta(years=1))
        self.assertFalse(contrato.vence_pronto)
        contrato._aplicar_reajustes(inicio)
        self.assertEqual((contrato.monto, contrato.fecha_renovacion), (1650000, False))
        self.assertEqual(contrato.fecha_reajuste, inicio + relativedelta(years=1))

    def test_renovar_un_contrato_vencido_ya_reajustado(self):
        # Venció hace 10 días y siguió vigente sin renovarse; el cron ya le aplicó el reajuste del aniversario.
        fin = self.hoy - timedelta(days=10)
        inicio = fin + timedelta(days=1) - relativedelta(years=1)
        contrato = self._activo(fecha_inicio=inicio, fecha_fin=fin, dia_pago=inicio.day, reajuste_pct=10)
        contrato.fecha_reajuste = fin + timedelta(days=1)
        contrato._aplicar_reajustes()
        self.assertEqual(contrato.monto, 1650000)
        # La renovación propone el alquiler de ahora, sin sumarle otro reajuste encima.
        asistente = self.env['alquiler.renovar.wizard'].with_context(default_contrato_id=contrato.id).create({})
        self.assertEqual((asistente.fecha_fin, asistente.monto), (fin + relativedelta(years=1), 1650000))
        asistente.action_confirmar()
        self.assertEqual((contrato.monto, contrato.fecha_renovacion), (1650000, False))
        self.assertEqual(contrato.fecha_reajuste, fin + timedelta(days=1) + relativedelta(years=1))
        nuevas = contrato._generar_cuotas()
        self.assertTrue(nuevas)
        self.assertEqual(set(nuevas.mapped('monto')), {1650000})

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
        self.assertIn('ese mes se paga en proporción a los días', html)

    def test_varias_empresas(self):
        contrato = self._activo()
        self._pagar(self._vencidas(contrato)[0])
        self.env.flush_all()
        antes = self.env['alquiler.panel'].datos()
        # Otra empresa, con su casa alquilada, un pago y un gasto.
        otra = self.env['res.company'].create({'name': 'Otra administradora'})
        casa = self.env['alquiler.propiedad'].create({
            'name': 'Casa de la otra', 'tipo': 'casa', 'ciudad': 'Luque', 'company_id': otra.id,
        })
        otro = self._activo(unidad_id=casa.unidad_ids.id, monto=900000)
        self._pagar(otro.cuota_ids.sorted('fecha_vencimiento')[0])
        self.env['alquiler.gasto'].create({'name': 'Pintura', 'propiedad_id': casa.id, 'monto': 300000})
        self.env.flush_all()

        # El Panel muestra solo la empresa activa.
        despues = self.env['alquiler.panel'].datos()
        self.assertEqual(despues['indicadores'], antes['indicadores'])
        self.assertEqual(despues['atender'], antes['atender'])
        self.assertNotIn(casa.id, [fila['id'] for fila in despues['propiedades']])
        de_la_otra = self.env['alquiler.panel'].with_company(otra).datos()
        self.assertEqual([fila['id'] for fila in de_la_otra['propiedades']], [casa.id])

        # Un usuario de la primera empresa no ve nada de la otra.
        usuario = new_test_user(self.env, login='admin_primera_empresa',
                                groups='base.group_user,alquileres.group_alquiler_admin',
                                company_id=self.env.company.id, company_ids=[Command.set(self.env.company.ids)])
        for modelo in ('alquiler.propiedad', 'alquiler.unidad', 'alquiler.contrato', 'alquiler.cuota',
                       'alquiler.pago', 'alquiler.gasto', 'alquiler.resultado'):
            self.assertFalse(self.env[modelo].with_user(usuario).search([('company_id', '=', otra.id)]), modelo)
        self.assertIn(self.edificio, self.env['alquiler.propiedad'].with_user(usuario).search([]))

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
