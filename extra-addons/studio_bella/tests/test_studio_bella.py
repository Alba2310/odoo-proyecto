# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from urllib.parse import unquote

import pytz

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, new_test_user, tagged

from odoo.addons.studio_bella.models.cita import numero_whatsapp
from odoo.addons.studio_bella.tests.common import StudioBellaCommon


@tagged('post_install', '-at_install')
class TestStudioBella(StudioBellaCommon):

    # Agenda

    def test_duracion_y_fin_salen_de_los_servicios(self):
        cita = self._cita(servicios=self.corte | self.color)
        self.assertEqual(cita.duracion, 150)
        self.assertEqual(cita.fecha_fin, self.lunes_10 + timedelta(minutes=150))
        self.assertEqual(cita.horario_texto, '10:00 a 12:30')
        self.assertEqual(cita.total, 300)

        sin_servicios = self._cita(inicio=self.lunes_10 + timedelta(hours=4), servicios=self.env['product.product'])
        self.assertEqual(sin_servicios.fecha_fin, sin_servicios.fecha_inicio + timedelta(minutes=30))

    def test_no_se_superponen_citas_del_mismo_estilista(self):
        cita = self._cita()
        with self.assertRaises(ValidationError):
            self._cita(inicio=self.lunes_10 + timedelta(minutes=30))
        # Termina justo cuando empieza la otra: no se pisan.
        self._cita(inicio=self.lunes_10 + timedelta(hours=1))
        # Si el cliente cancela, el horario queda libre.
        cita.action_cancelar()
        self._cita(inicio=self.lunes_10 + timedelta(minutes=30), servicios=self.env['product.product'])

    def test_solo_dentro_del_horario_del_estilista(self):
        with self.assertRaises(ValidationError):
            self._cita(inicio=datetime(2026, 11, 1, 13, 0))  # domingo
        with self.assertRaises(ValidationError):
            self._cita(inicio=datetime(2026, 11, 2, 21, 30))  # lunes de 18:30 a 19:30, cierra a las 19:00
        with self.assertRaises(ValidationError):
            self._cita(inicio=datetime(2026, 11, 2, 10, 30))  # lunes 7:30, abre a las 8:00
        # Un feriado cargado en el horario también bloquea la agenda.
        self.env['resource.calendar.leaves'].create({
            'name': 'Feriado de prueba',
            'calendar_id': self.horario.id,
            'date_from': datetime(2026, 11, 2, 3, 0),
            'date_to': datetime(2026, 11, 3, 2, 59),
        })
        with self.assertRaises(ValidationError):
            self._cita()

    def test_el_estilista_tiene_que_hacer_el_servicio(self):
        with self.assertRaises(ValidationError):
            self._cita(servicios=self.manicura)
        # Sin servicios configurados, hace todos.
        self.estilista.bella_servicio_ids = False
        self._cita(servicios=self.manicura)

    def test_cambiar_el_horario_vuelve_a_mandar_el_recordatorio(self):
        cita = self._cita()
        cita.recordatorio_enviado = True
        cita.fecha_inicio = self.lunes_10 + timedelta(hours=2)
        self.assertFalse(cita.recordatorio_enviado)

    # Cobro

    def test_cobrar_cita_factura_paga_y_descuenta_stock(self):
        cita = self._cita(servicios=self.corte | self.color,
                          producto_ids=[Command.create({'producto_id': self.shampoo.id, 'cantidad': 2})])
        cita.action_iniciar()
        vuelto = self._cobrar(cita, monto_recibido=500)

        self.assertEqual(vuelto, 100)
        self.assertEqual(cita.estado, 'cobrada')
        self.assertEqual(cita.metodo_pago, 'efectivo')
        factura = cita.factura_id
        self.assertEqual(factura.state, 'posted')
        self.assertEqual(factura.partner_id, self.cliente)
        # Precios con IVA incluido: el total de la factura es lo que se cobró.
        self.assertAlmostEqual(factura.amount_total, 400)
        self.assertAlmostEqual(factura.amount_tax, 400 / 11, places=2)
        self.assertIn(factura.payment_state, ('paid', 'in_payment'))
        # Shampoo vendido: 5 - 2. Tinte usado en el color: 1 - 1.
        self.assertEqual(self._stock(self.shampoo), 3)
        self.assertEqual(self._stock(self.tinte), 0)
        self.assertEqual(len(cita.movimiento_ids), 2)
        self.assertTrue(all(movimiento.state == 'done' for movimiento in cita.movimiento_ids))

        with self.assertRaises(UserError):
            cita.action_cancelar()
        with self.assertRaises(UserError):
            cita.unlink()

    def test_cobrar_con_tarjeta_va_al_banco(self):
        cita = self._cita()
        self._cobrar(cita, metodo='tarjeta')
        pago = cita.factura_id.matched_payment_ids or cita.factura_id._get_reconciled_payments()
        self.assertEqual(pago.journal_id.type, 'bank')

    def test_no_se_vende_sin_stock_pero_los_insumos_no_frenan_el_cobro(self):
        cita = self._cita(producto_ids=[Command.create({'producto_id': self.shampoo.id, 'cantidad': 6})])
        with self.assertRaises(UserError):
            self._cobrar(cita)
        self.assertEqual(cita.estado, 'agendada')
        self.assertFalse(cita.factura_id)

        # Dos colores gastan 2 tintes y hay 1: se cobra igual y el stock queda en negativo.
        otra = self._cita(inicio=self.lunes_10 + timedelta(hours=3), servicios=[self.color, self.color])
        self._cobrar(otra)
        self.assertEqual(otra.estado, 'cobrada')
        self.assertEqual(self._stock(self.tinte), -1)

    def test_efectivo_insuficiente(self):
        cita = self._cita()
        with self.assertRaises(UserError):
            self._cobrar(cita, monto_recibido=50)
        self.assertEqual(cita.estado, 'agendada')

    def test_solo_se_pasa_a_cobrada_con_el_boton(self):
        cita = self._cita()
        with self.assertRaises(UserError):
            cita.estado = 'cobrada'  # por ejemplo, arrastrando la tarjeta en el kanban
        cita.action_no_asistio()
        with self.assertRaises(UserError):
            cita.action_cobrar()
        cita.action_reagendar()
        self.assertEqual(cita.estado, 'agendada')

    def test_venta_de_mostrador(self):
        venta = self.env['bella.venta'].create({
            'linea_ids': [Command.create({'producto_id': self.shampoo.id, 'cantidad': 1})],
        })
        self.assertEqual(venta.cliente_id, self.env.ref('studio_bella.cliente_consumidor_final'))
        self.assertEqual(venta.total, 50)
        vuelto = self._cobrar(venta, monto_recibido=100)
        self.assertEqual(vuelto, 50)
        self.assertEqual(venta.estado, 'cobrada')
        self.assertAlmostEqual(venta.factura_id.amount_total, 50)
        self.assertEqual(self._stock(self.shampoo), 4)
        with self.assertRaises(UserError):
            venta.action_cancelar()

    # Recordatorios

    def test_recordatorio_de_las_citas_de_manana(self):
        # Estilista sin horario fijo, para que la prueba ande cualquier día de la semana.
        self.estilista.resource_calendar_id = False
        tz = pytz.timezone('America/Asuncion')
        manana = datetime.now(tz).date() + timedelta(days=1)
        manana_10 = tz.localize(datetime.combine(manana, datetime.min.time()).replace(hour=10))
        manana_10 = manana_10.astimezone(pytz.utc).replace(tzinfo=None)

        de_manana = self._cita(inicio=manana_10)
        pasado = self._cita(inicio=manana_10 + timedelta(days=2))
        cancelada = self._cita(inicio=manana_10 + timedelta(hours=3))
        cancelada.action_cancelar()

        self.env['bella.cita']._cron_enviar_recordatorios()
        self.assertTrue(de_manana.recordatorio_enviado)
        self.assertEqual(de_manana.recordatorio_canal, 'correo')
        self.assertFalse(pasado.recordatorio_enviado)
        self.assertFalse(cancelada.recordatorio_enviado)
        mensaje = de_manana.message_ids.filtered(lambda m: self.cliente in m.partner_ids)
        self.assertEqual(len(mensaje), 1)
        self.assertIn('Recordatorio', mensaje.subject)

        # Si se vuelve a correr la tarea, no se manda dos veces.
        self.env['bella.cita']._cron_enviar_recordatorios()
        self.assertEqual(len(de_manana.message_ids.filtered(lambda m: self.cliente in m.partner_ids)), 1)

    def test_recordatorio_manual_necesita_correo(self):
        cita = self._cita()
        cita.cliente_id.email = False
        with self.assertRaises(UserError):
            cita.action_enviar_recordatorio()

    def test_numero_de_whatsapp(self):
        self.assertEqual(numero_whatsapp('0981 234 567'), '595981234567')
        self.assertEqual(numero_whatsapp('981234567'), '595981234567')
        self.assertEqual(numero_whatsapp('+595 981 234-567'), '595981234567')
        self.assertEqual(numero_whatsapp('00595 981 234 567'), '595981234567')
        self.assertEqual(numero_whatsapp('+54 9 11 1234-5678'), '5491112345678')
        self.assertEqual(numero_whatsapp(False), '')

    def test_recordatorio_por_whatsapp(self):
        self.company.country_id = self.env.ref('base.py')
        self.cliente.write({'phone': '0981 234 567', 'email': False})
        cita = self._cita()
        accion = cita.action_whatsapp()

        self.assertEqual(accion['type'], 'ir.actions.act_url')
        self.assertTrue(accion['url'].startswith('https://wa.me/595981234567?text='))
        texto = unquote(accion['url'].split('text=')[1])
        self.assertIn('Cliente de prueba', texto)
        self.assertIn('Corte de prueba', texto)
        self.assertIn('10:00', texto)
        self.assertTrue(cita.recordatorio_enviado)
        self.assertEqual(cita.recordatorio_canal, 'whatsapp')

        # Si se cambia el horario, hay que volver a avisar.
        cita.fecha_inicio = self.lunes_10 + timedelta(hours=2)
        self.assertFalse(cita.recordatorio_enviado)
        self.assertFalse(cita.recordatorio_canal)

        self.cliente.phone = False
        with self.assertRaises(UserError):
            cita.action_whatsapp()

    # Compras y stock mínimo

    def test_stock_minimo_avisa_y_se_cierra_al_recibir_mercaderia(self):
        plantilla = self.shampoo.product_tmpl_id
        plantilla.write({'bella_stock_minimo': 4, 'bella_stock_maximo': 10})
        regla = self.env['stock.warehouse.orderpoint'].search([('product_id', '=', self.shampoo.id)])
        self.assertEqual((regla.product_min_qty, regla.product_max_qty), (4, 10))
        self.assertEqual(regla.warehouse_id, self.warehouse)
        self.assertFalse(plantilla.bella_por_reponer)  # Hay 5.

        def avisos():
            return plantilla.activity_ids.filtered(lambda actividad: actividad.summary == 'Reponer stock')

        # Se venden 2 en una cita: quedan 3, menos que el mínimo.
        cita = self._cita(producto_ids=[Command.create({'producto_id': self.shampoo.id, 'cantidad': 2})])
        self._cobrar(cita)
        plantilla.invalidate_recordset()
        self.assertTrue(plantilla.bella_por_reponer)
        self.assertIn(plantilla, self.env['product.template'].search([('bella_por_reponer', '=', True)]))
        self.assertEqual(len(avisos()), 1)
        self.assertIn('Conviene pedir 7', str(avisos().note))

        # La revisión diaria no repite el aviso.
        self.env['product.template']._bella_avisar_reposicion()
        self.assertEqual(len(avisos()), 1)

        # Llega el pedido del proveedor: sube el stock y se cierra el aviso.
        proveedor = self.env['res.partner'].create({'name': 'Proveedor de prueba'})
        compra = self.env['purchase.order'].create({
            'partner_id': proveedor.id,
            'order_line': [Command.create({'product_id': self.shampoo.id, 'product_qty': 7, 'price_unit': 30})],
        })
        compra.button_confirm()
        compra.picking_ids.with_context(skip_sms=True).button_validate()
        self.assertEqual(compra.picking_ids.state, 'done')
        self.assertEqual(self._stock(self.shampoo), 10)
        self.assertFalse(avisos())

    def test_stock_minimo_al_crear_el_producto(self):
        producto = self.env['product.template'].create({
            'name': 'Cera de prueba', 'type': 'consu', 'is_storable': True,
            'bella_stock_minimo': 2, 'bella_stock_maximo': 6,
        })
        self.assertEqual((producto.bella_stock_minimo, producto.bella_stock_maximo), (2, 6))
        self.assertTrue(producto.bella_por_reponer)  # Todavía no hay stock.

    # Permisos

    def test_recepcion_agenda_y_cobra_sin_permisos_de_empleados(self):
        recepcion = new_test_user(
            self.env, login='recepcion_bella', groups='studio_bella.group_bella_recepcion',
            company_id=self.company.id, company_ids=[Command.set(self.company.ids)],
        )
        self.assertFalse(recepcion.has_group('hr.group_hr_user'))
        env = self.env(user=recepcion)
        estilistas = env['hr.employee'].search([('bella_estilista', '=', True)])
        self.assertIn(self.estilista.id, estilistas.ids)

        cita = env['bella.cita'].create({
            'cliente_id': self.cliente.id,
            'estilista_id': self.estilista.id,
            'fecha_inicio': self.lunes_10,
            'servicio_ids': [Command.create({'servicio_id': self.corte.id})],
            'producto_ids': [Command.create({'producto_id': self.shampoo.id, 'cantidad': 1})],
        })
        self.assertEqual(cita.estilista_id.name, 'Estilista de prueba')
        with self.assertRaises(ValidationError):
            env['bella.cita'].create({
                'cliente_id': self.cliente.id,
                'estilista_id': self.estilista.id,
                'fecha_inicio': self.lunes_10 + timedelta(hours=2),
                'servicio_ids': [Command.create({'servicio_id': self.manicura.id})],
            })

        wizard = Form(env['bella.cobro.wizard'].with_context(default_cita_id=cita.id)).save()
        wizard.action_cobrar()
        self.assertEqual(cita.estado, 'cobrada')
        self.assertEqual(cita.factura_id.state, 'posted')
        self.assertEqual(self._stock(self.shampoo), 4)
