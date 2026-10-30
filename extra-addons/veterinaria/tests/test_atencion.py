# -*- coding: utf-8 -*-
from datetime import date, datetime, timedelta
from urllib.parse import unquote

from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, new_test_user, tagged

from odoo.addons.veterinaria.models.utiles import edad_texto, numero_whatsapp
from odoo.addons.veterinaria.tests.common import PatitasCommon


@tagged('post_install', '-at_install')
class TestAtencion(PatitasCommon):

    # Agenda

    def test_duracion_y_total_salen_de_lo_que_se_hace(self):
        atencion = self._atencion(productos=self.consulta | self.antirrabica)
        self.assertEqual(atencion.duracion, 45)
        self.assertEqual(atencion.fecha_fin, self.lunes_10 + timedelta(minutes=45))
        self.assertEqual(atencion.total, 160)
        self.assertEqual(atencion.dueno_id, self.duena)
        self.assertEqual(atencion.hora_texto, '10:00')

        sin_nada = self._atencion(inicio=self.lunes_10 + timedelta(hours=3), productos=self.env['product.product'])
        self.assertEqual(sin_nada.fecha_fin, sin_nada.fecha_inicio + timedelta(minutes=30))

    def test_no_se_pisan_los_turnos_del_mismo_profesional(self):
        atencion = self._atencion()
        with self.assertRaises(ValidationError):
            self._atencion(inicio=self.lunes_10 + timedelta(minutes=15))
        # Termina justo cuando empieza el otro: no se pisan.
        self._atencion(inicio=self.lunes_10 + timedelta(minutes=30))
        # Si cancela, el horario queda libre.
        atencion.action_cancelar()
        self._atencion(productos=self.antirrabica)

    def test_el_que_llega_sin_turno_no_ocupa_la_agenda(self):
        self._atencion()
        sin_turno = self._atencion(origen='sin_turno')
        self.assertEqual(sin_turno.estado, 'en_espera')
        self.assertTrue(sin_turno.llegada)

    def test_solo_dentro_del_horario(self):
        with self.assertRaises(ValidationError):
            self._atencion(inicio=datetime(2026, 11, 1, 13, 0))  # domingo
        with self.assertRaises(ValidationError):
            self._atencion(inicio=datetime(2026, 11, 2, 21, 45))  # lunes de 18:45 a 19:15: cierra a las 19:00
        with self.assertRaises(ValidationError):
            self._atencion(inicio=datetime(2026, 11, 7, 16, 0))  # sábado a las 13:00: ya cerró
        self._atencion(inicio=datetime(2026, 11, 7, 15, 30))  # sábado de 12:30 a 13:00
        # Un feriado cargado en el horario también cierra la agenda.
        self.env['resource.calendar.leaves'].create({
            'name': 'Feriado de prueba',
            'calendar_id': self.horario.id,
            'date_from': datetime(2026, 11, 3, 3, 0),
            'date_to': datetime(2026, 11, 4, 2, 59),
        })
        with self.assertRaises(ValidationError):
            self._atencion(inicio=self.lunes_10 + timedelta(days=1))

    def test_el_profesional_tiene_que_ser_del_area(self):
        with self.assertRaises(ValidationError):
            self._atencion(profesional_id=self.peluquera.id)
        atencion = self._atencion(area='estetica', productos=self.bano, profesional_id=self.peluquera.id)
        self.assertEqual(atencion.duracion, 60)
        # Con servicios cargados, solo hace esos.
        self.veterinaria.vet_servicio_ids = [Command.set(self.consulta.ids)]
        ecografia = self.env['product.product'].create({
            'name': 'Ecografía de prueba', 'type': 'service', 'vet_area': 'consultorio', 'vet_duracion': 30,
        })
        with self.assertRaises(ValidationError):
            self._atencion(productos=ecografia)
        # Una vacuna (no es un servicio) la aplica cualquiera del consultorio.
        self._atencion(productos=self.antirrabica)

    def test_sin_turno_lo_atiende_quien_aprieta_el_boton(self):
        atencion = self.env['vet.atencion'].create({
            'mascota_id': self.toby.id, 'origen': 'sin_turno', 'motivo': 'Se lastimó la pata',
        })
        self.assertFalse(atencion.profesional_id)
        self.assertEqual(atencion.estado, 'en_espera')
        with self.assertRaises(UserError):
            atencion.action_atender()
        self.veterinaria.user_id = self.env.user
        atencion.action_atender()
        self.assertEqual(atencion.profesional_id, self.veterinaria)
        self.assertEqual(atencion.estado, 'en_curso')
        # Un turno común sí necesita a alguien.
        with self.assertRaises(ValidationError):
            self._atencion(profesional_id=False)

    # Recorrido, historia clínica y carnet

    def test_recorrido_carnet_y_peso(self):
        atencion = self._atencion(productos=self.consulta | self.antirrabica)
        atencion.linea_ids.filtered(lambda linea: linea.producto_id == self.antirrabica).lote = 'L-2026'
        atencion.action_llego()
        self.assertEqual(atencion.estado, 'en_espera')
        atencion.action_atender()
        atencion.write({'peso': 12.4, 'temperatura': 38.5, 'diagnostico': 'Sano'})
        self.assertEqual(self.toby.peso_actual, 12.4)
        atencion.action_terminar()
        self.assertEqual(atencion.estado, 'lista')
        self.assertTrue(atencion.fin_atencion)

        aplicacion = atencion.aplicacion_ids
        self.assertEqual(len(aplicacion), 1)
        self.assertEqual(aplicacion.producto_id, self.antirrabica)
        self.assertEqual(aplicacion.fecha, date(2026, 11, 2))
        self.assertEqual(aplicacion.proxima_fecha, date(2027, 11, 2))
        self.assertEqual(aplicacion.lote, 'L-2026')
        self.assertEqual(self.toby.proxima_dosis, date(2027, 11, 2))
        # Cobrarla no la anota dos veces.
        self._cobrar(atencion)
        self.assertEqual(len(atencion.aplicacion_ids), 1)
        # Cambiar el peso cambia el del historial (no agrega otro).
        atencion.peso = 12.6
        self.assertEqual(len(self.toby.peso_ids), 1)
        self.assertEqual(self.toby.peso_actual, 12.6)

    def test_arrastrar_en_el_tablero(self):
        personal = new_test_user(self.env, login='recepcion_patitas', groups='veterinaria.group_vet_personal')
        atencion = self._atencion(productos=self.consulta | self.antirrabica).with_user(personal)
        # Hacia adelante, como los botones: de "Turnos de hoy" directo a "Para retirar y cobrar".
        atencion.action_mover('lista')
        self.assertEqual(atencion.estado, 'lista')
        self.assertTrue(atencion.llegada and atencion.inicio_atencion and atencion.fin_atencion)
        self.assertEqual(len(atencion.aplicacion_ids), 1)
        # Hacia atrás deshace: ya no está terminada y lo del carnet se borra hasta que se vuelva a terminar.
        atencion.action_mover('en_espera')
        self.assertEqual(atencion.estado, 'en_espera')
        self.assertTrue(atencion.llegada)
        self.assertFalse(atencion.inicio_atencion or atencion.fin_atencion)
        self.assertFalse(atencion.aplicacion_ids)
        self.assertIn('Se volvió de', atencion.message_ids[0].body)
        atencion.action_mover('reservada')
        self.assertFalse(atencion.llegada)
        atencion.action_mover('en_curso')
        atencion.action_mover('lista')
        self.assertEqual(len(atencion.aplicacion_ids), 1)
        # A "Cobrada" solo con el botón Cobrar.
        with self.assertRaises(UserError):
            atencion.action_mover('cobrada')
        # Quien llegó sin turno no tiene un turno al que volver.
        sin_turno = self.env['vet.atencion'].create({'mascota_id': self.toby.id, 'origen': 'sin_turno'})
        with self.assertRaises(UserError):
            sin_turno.with_user(personal).action_mover('reservada')

    def test_no_se_pasa_a_cobrada_sin_el_boton(self):
        atencion = self._atencion()
        with self.assertRaises(UserError):
            atencion.estado = 'cobrada'

    def test_de_la_consulta_a_la_internacion(self):
        atencion = self._atencion(diagnostico='Gastroenteritis')
        accion = atencion.action_internar()
        estadia = self.env['vet.internacion'].with_context(**accion['context']).create({'lugar_id': self.jaula.id})
        self.assertEqual(estadia.mascota_id, self.toby)
        self.assertEqual(estadia.motivo, 'Gastroenteritis')
        self.assertEqual(estadia.atencion_id, atencion)
        self.assertEqual(estadia.producto_dia_id, self.dia_internacion)

    # Cobro

    def test_cobro_mixto(self):
        atencion = self._atencion(productos=self.consulta | self.antirrabica)
        atencion.action_terminar()
        vuelto = self._cobrar(atencion, tarjeta=100, entrega=100)
        self.assertEqual(vuelto, 40)
        factura = atencion.factura_id
        self.assertEqual(atencion.estado, 'cobrada')
        self.assertEqual(factura.state, 'posted')
        self.assertEqual(factura.amount_total, 160)
        self.assertIn(factura.payment_state, ('paid', 'in_payment'))
        pagos = self.env['account.payment'].search([('partner_id', '=', self.duena.id)])
        self.assertEqual(sorted(pagos.mapped('amount')), [60, 100])
        self.assertEqual(sorted(pagos.journal_id.mapped('type')), ['bank', 'cash'])
        self.assertIn('Tarjeta', atencion.forma_pago)
        self.assertIn('Efectivo', atencion.forma_pago)
        self.assertEqual(self._stock(self.antirrabica), 2)
        # Cobrada, sus líneas no cambian.
        with self.assertRaises(UserError):
            atencion.linea_ids[0].precio_unitario = 1
        with self.assertRaises(UserError):
            atencion.unlink()

    def test_los_pagos_tienen_que_sumar_el_total(self):
        atencion = self._atencion()
        wizard = Form(self.env['vet.cobro.wizard'].with_context(default_atencion_id=atencion.id))
        wizard.tarjeta = 30
        wizard.efectivo = 30
        wizard = wizard.save()
        self.assertEqual(wizard.falta, 40)
        with self.assertRaises(UserError):
            wizard.action_cobrar()
        self.assertFalse(atencion.factura_id)
        # Los botones "todo con..." ponen el total en una sola forma de pago.
        wizard.action_todo_transferencia()
        self.assertEqual((wizard.efectivo, wizard.tarjeta, wizard.transferencia), (0, 0, 100))

    def test_sin_stock_no_se_vende(self):
        venta = self.env['vet.venta'].create({
            'linea_ids': [Command.create({'producto_id': self.alimento.id, 'cantidad': 6})],
        })
        self.assertEqual(venta.dueno_id, self.env.ref('veterinaria.cliente_consumidor_final'))
        with self.assertRaises(UserError):
            self._cobrar(venta)
        venta.linea_ids.cantidad = 2
        self._cobrar(venta, transferencia=400)
        self.assertEqual(venta.estado, 'cobrada')
        self.assertEqual(venta.forma_pago.split(' ')[0], 'Transferencia')
        self.assertEqual(self._stock(self.alimento), 3)

    # Avisos

    def test_aviso_lista_para_retirar(self):
        atencion = self._atencion(area='estetica', productos=self.bano, profesional_id=self.peluquera.id)
        atencion.estetica_observaciones = 'Tenía unas pulgas, le pusimos pipeta.'
        with self.assertRaises(UserError):
            atencion.action_avisar_lista()
        atencion.action_terminar()
        accion = atencion.action_avisar_lista()
        self.assertTrue(accion['url'].startswith('https://wa.me/595981000900?text='))
        texto = unquote(accion['url'])
        self.assertIn('¡Hola Ana! Toby ya está listo y perfumado', texto)
        self.assertIn('pulgas', texto)
        self.assertTrue(atencion.aviso_lista_el)

    def test_recordatorio_por_correo_el_dia_antes(self):
        ahora = fields.Datetime.now()
        manana = self._atencion(inicio=ahora + timedelta(days=1), sin_horario=True)
        mas_adelante = self._atencion(inicio=ahora + timedelta(days=3), sin_horario=True)
        self.env['vet.atencion']._cron_recordatorios()
        self.assertTrue(manana.recordatorio_enviado)
        self.assertFalse(mas_adelante.recordatorio_enviado)
        self.assertIn('tiene turno', manana.message_ids[0].subject)
        # Si se cambia el horario, se vuelve a avisar.
        manana.fecha_inicio = manana.fecha_inicio + timedelta(minutes=30)
        self.assertFalse(manana.recordatorio_enviado)

    # Textos

    def test_numero_whatsapp_y_edad(self):
        self.assertEqual(numero_whatsapp('0981 234 567'), '595981234567')
        self.assertEqual(numero_whatsapp('+54 9 11 1234-5678'), '5491112345678')
        self.assertEqual(edad_texto(date(2022, 3, 10), date(2026, 11, 2)), '4 años y 7 meses')
        self.assertEqual(edad_texto(date(2026, 9, 2), date(2026, 11, 2)), '2 meses')
        self.assertEqual(edad_texto(date(2026, 10, 20), date(2026, 11, 2)), '13 días')
        self.assertEqual(edad_texto(date(2025, 11, 2), date(2026, 11, 2)), '1 año')
