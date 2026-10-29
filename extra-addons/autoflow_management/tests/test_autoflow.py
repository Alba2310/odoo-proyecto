# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, new_test_user, tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestAutoflow(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.groups_id += cls.env.ref('autoflow_management.group_autoflow_manager')
        cls.warehouse = cls.env['stock.warehouse'].search([('company_id', '=', cls.env.company.id)], limit=1)

        brand = cls.env['autoflow.vehicle.brand'].create({'name': 'Marca de prueba'})
        cls.vehicle_model = cls.env['autoflow.vehicle.model'].create({'name': 'Modelo X', 'brand_id': brand.id})
        cls.vehicle = cls._create_vehicle('TSTVHC00000000001', odometer=1000)
        cls.customer = cls.env['res.partner'].create({'name': 'Cliente de prueba', 'email': 'cliente@example.com'})
        cls.mechanic = cls.env['hr.employee'].create({'name': 'Mecánico de prueba'})

        cls.part = cls.env['product.product'].create({
            'name': 'Filtro de prueba', 'type': 'consu', 'is_storable': True, 'list_price': 50,
        })
        cls.env['stock.quant']._update_available_quantity(cls.part, cls.warehouse.lot_stock_id, 10)
        cls.labor_product = cls.env.ref('autoflow_management.product_workshop_labor')
        cls.start = datetime(2026, 10, 20, 10, 0)

    @classmethod
    def _create_vehicle(cls, vin, **values):
        return cls.env['autoflow.vehicle'].create({
            'model_id': cls.vehicle_model.id, 'year': 2025, 'vin': vin, **values,
        })

    def _test_drive(self, start=None, minutes=30, **values):
        start = start or self.start
        return self.env['autoflow.test.drive'].create({
            'partner_id': self.customer.id,
            'vehicle_id': self.vehicle.id,
            'date_start': start,
            'date_end': start + timedelta(minutes=minutes),
            **values,
        })

    def _order(self, **values):
        return self.env['autoflow.workshop.order'].create({
            'partner_id': self.customer.id,
            'vehicle_id': self.vehicle.id,
            'mechanic_id': self.mechanic.id,
            'odometer': 1500,
            'labor_line_ids': [Command.create({'name': 'Service', 'hours': 2, 'price_unit': 100})],
            'part_line_ids': [Command.create({'product_id': self.part.id, 'quantity': 3})],
            **values,
        })

    def _sale(self):
        return self.env['sale.order'].create({'partner_id': self.customer.id, 'vehicle_id': self.vehicle.id})

    def _ready_to_finish(self, order):
        order.inspection_line_ids[:1].state = 'change'
        order.action_inspection_mark_ok()
        self.assertEqual(order.inspection_line_ids[:1].state, 'change', 'Solo marca los que estaban sin revisar')
        self.assertFalse(order.inspection_pending_count)
        order.action_ready()

    # Vehículos

    def test_vin_validation(self):
        with self.assertRaises(ValidationError):
            self._create_vehicle('CORTO123')
        with self.assertRaises(ValidationError, msg='El VIN no usa la letra O'):
            self._create_vehicle('OOOOOOOOOOOOOOOOO')
        vehicle = self._create_vehicle('tst vhc 00000000002')
        self.assertEqual(vehicle.vin, 'TSTVHC00000000002', 'El VIN se guarda en mayúsculas y sin espacios')
        self.assertEqual(vehicle.name, 'Marca de prueba Modelo X 2025')

    def test_acquisition_cost_only_for_manager(self):
        user = new_test_user(self.env, login='asesor_autoflow',
                             groups='base.group_user,autoflow_management.group_autoflow_user',
                             company_id=self.env.company.id, company_ids=[Command.set(self.env.company.ids)])
        vehicle = self.vehicle.with_user(user)
        self.assertEqual(vehicle.read(['odometer'])[0]['odometer'], 1000, 'El usuario ve el vehículo')
        self.assertFalse(vehicle.fields_get(['acquisition_cost']), 'Solo el Responsable ve el costo')
        with self.assertRaises(AccessError):
            vehicle.read(['acquisition_cost'])

    # Pruebas de manejo

    def test_test_drive_rejects_vehicle_in_maintenance_or_sold(self):
        for state in ('maintenance', 'sold'):
            self.vehicle.state = state
            with self.assertRaises(ValidationError):
                self._test_drive()
        self.vehicle.state = 'reserved'
        self.assertTrue(self._test_drive(), 'Un vehículo reservado se puede probar')

    def test_test_drive_overlap(self):
        first = self._test_drive()
        with self.assertRaises(ValidationError):
            self._test_drive(start=self.start + timedelta(minutes=15))
        # Pegada a la anterior no se solapa.
        self._test_drive(start=self.start + timedelta(minutes=30))
        # Una cancelada libera el horario.
        first.action_cancel()
        self._test_drive(start=self.start + timedelta(minutes=5), minutes=20)

    def test_test_drive_dates_and_odometer(self):
        with self.assertRaises(ValidationError):
            self._test_drive(minutes=-10)
        drive = self._test_drive()
        drive.action_start()
        self.assertEqual(drive.odometer_start, 1000, 'Toma el kilometraje del vehículo al salir')
        with self.assertRaises(ValidationError):
            drive.odometer_end = 900

    def test_test_drive_start_takes_current_odometer(self):
        # Agendada con días de anticipación: el formulario propuso 1000 km, pero el auto anduvo desde entonces.
        drive = self._test_drive(odometer_start=1000)
        self.vehicle.odometer = 1300
        drive.action_start()
        self.assertEqual(drive.odometer_start, 1300, 'Vale el kilometraje del vehículo al salir')
        later = self._test_drive(start=self.start + timedelta(days=1), odometer_start=1350)
        later.action_start()
        self.assertEqual(later.odometer_start, 1350, 'Si al salir se cargó uno mayor, se respeta')

    def test_test_drive_done_updates_vehicle_odometer(self):
        drive = self._test_drive()
        drive.action_start()
        with self.assertRaises(UserError, msg='Hay que cargar el kilometraje al volver'):
            drive.action_done()
        drive.odometer_end = 1042
        drive.action_done()
        self.assertEqual(drive.state, 'done')
        self.assertEqual(drive.distance, 42)
        self.assertEqual(self.vehicle.odometer, 1042)

    def test_test_drive_display_name(self):
        drive = self._test_drive()
        self.assertEqual(drive.display_name, f'{drive.name} · Cliente de prueba',
                         'En el calendario y en la cotización se ve a qué cliente corresponde')

    def test_test_drive_onchange_vehicle(self):
        with Form(self.env['autoflow.test.drive']) as form:
            form.partner_id = self.customer
            form.vehicle_id = self.vehicle
            self.assertEqual(form.odometer_start, 1000)

    def test_test_drive_creates_quotation(self):
        self.vehicle.write({
            'product_id': self.env['product.product'].create({'name': 'Vehículo 0 km'}).id,
            'sale_price': 30000,
        })
        drive = self._test_drive()
        action = drive.action_create_quotation()
        order = self.env['sale.order'].browse(action['res_id'])
        self.assertEqual((order.partner_id, order.vehicle_id, order.test_drive_id),
                         (self.customer, self.vehicle, drive))
        self.assertEqual(order.amount_untaxed, 30000)

        order.action_confirm()
        self.assertEqual(self.vehicle.state, 'sold')
        self.assertEqual(self.vehicle.partner_id, self.customer)
        order._action_cancel()
        self.assertEqual(self.vehicle.state, 'available')

    def test_sale_cancelled_while_vehicle_in_workshop(self):
        # Vendido y después al taller: si se cancela la venta, al salir del taller queda disponible.
        sale = self._sale()
        sale.action_confirm()
        order = self._order()
        self.assertEqual(self.vehicle.state, 'maintenance')
        with self.assertRaises(UserError, msg='Aunque esté en el taller, ya está vendido'):
            self._sale().action_confirm()
        sale._action_cancel()
        self.assertEqual(self.vehicle.state, 'maintenance', 'Sigue en el taller')
        order.action_cancel()
        self.assertEqual(self.vehicle.state, 'available')
        self.assertFalse(self.vehicle.partner_id)

        # Vendido mientras está en el taller y la venta se cancela antes de que salga: sigue en el taller.
        order.action_reopen()
        sale = self._sale()
        sale.action_confirm()
        self.assertEqual(self.vehicle.state, 'sold')
        sale._action_cancel()
        self.assertEqual(self.vehicle.state, 'maintenance')
        order.action_cancel()
        self.assertEqual(self.vehicle.state, 'available')

    # Órdenes de servicio

    def test_order_sequence_and_vehicle_state(self):
        self.vehicle.state = 'reserved'
        order = self._order()
        self.assertTrue(order.name.startswith(f'OS/{fields.Date.today().year}/'))
        self.assertEqual(self.vehicle.state, 'maintenance')
        self.assertEqual(len(order.inspection_line_ids), self.env['autoflow.inspection.item'].search_count([]),
                         'La orden arranca con todo el checklist')
        with self.assertRaises(ValidationError, msg='Un vehículo no puede tener dos órdenes abiertas'):
            self._order()
        order.action_cancel()
        self.assertEqual(self.vehicle.state, 'reserved', 'Al salir del taller recupera su estado anterior')
        order.action_reopen()
        self.assertEqual(self.vehicle.state, 'maintenance')

    def test_order_amounts(self):
        order = self._order()
        self.assertEqual(order.labor_hours, 2)
        self.assertEqual(order.amount_labor, 200)
        self.assertEqual(order.amount_parts, 150, 'El precio del repuesto sale del producto')
        self.assertEqual(order.amount_total, 350)
        order.part_line_ids.quantity = 4
        self.assertEqual(order.amount_total, 400)

    def test_order_ready_notifies_customer(self):
        order = self._order()
        self.assertFalse(order.activity_ids)
        order.action_ready()
        message = order.message_ids.filtered(lambda m: self.customer in m.partner_ids)
        self.assertEqual(len(message), 1)
        self.assertIn('listo', message.subject)
        self.assertEqual(len(order.activity_ids), 1, 'El asesor recibe una actividad para coordinar la entrega')

    def test_order_done_invoices_consumes_stock_and_updates_odometer(self):
        self.vehicle.state = 'sold'
        order = self._order()
        self._ready_to_finish(order)
        # Igual que arrastrar la tarjeta a la columna "Finalizado" en el kanban.
        order.write({'state': 'done'})

        self.assertTrue(order.date_done)
        self.assertEqual(self.vehicle.odometer, 1500)
        self.assertEqual(self.vehicle.state, 'sold')
        self.assertEqual(self.part.with_context(location=self.warehouse.lot_stock_id.id).qty_available, 7)
        self.assertEqual(order.stock_move_ids.state, 'done')

        invoice = order.invoice_id
        self.assertEqual((invoice.state, invoice.move_type, invoice.partner_id, invoice.invoice_origin),
                         ('draft', 'out_invoice', self.customer, order.name))
        product_lines = invoice.invoice_line_ids.filtered(lambda line: line.display_type == 'product')
        self.assertEqual(product_lines.product_id, self.labor_product | self.part)
        self.assertEqual(invoice.amount_untaxed, 350)

        with self.assertRaises(UserError, msg='Una orden finalizada no vuelve atrás'):
            order.write({'state': 'repair'})

    def test_order_done_checks(self):
        order = self._order(mechanic_id=False)
        with self.assertRaises(UserError) as error:
            order.action_done()
        self.assertIn('mecánico', str(error.exception))
        self.assertIn('checklist', str(error.exception))
        self.assertEqual(order.state, 'received')

        order.mechanic_id = self.mechanic
        order.part_line_ids.quantity = 11
        self._ready_to_finish(order)
        self.assertFalse(order.parts_available)
        with self.assertRaises(UserError, msg='No alcanza el stock del repuesto'):
            order.action_done()
        self.assertFalse(order.invoice_id)

    def test_order_done_sums_stock_per_product(self):
        # Dos líneas del mismo repuesto: 6 + 6 con 10 en el depósito no alcanzan.
        order = self._order(part_line_ids=[Command.create({'product_id': self.part.id, 'quantity': 6}),
                                           Command.create({'product_id': self.part.id, 'quantity': 6})])
        self._ready_to_finish(order)
        self.assertFalse(order.parts_available)
        with self.assertRaises(UserError) as error:
            order.action_done()
        self.assertIn('se necesitan 12', str(error.exception))
        self.assertEqual(self.part.with_context(location=self.warehouse.lot_stock_id.id).qty_available, 10)

    def test_order_done_validates_unsaved_changes(self):
        # Clic en "Finalizado" de la barra de estado con cambios sin guardar: llegan en la misma escritura
        # que la etapa y se valida la orden como va a quedar.
        no_stock = self.env['product.product'].create({'name': 'Correa sin stock', 'type': 'consu',
                                                       'is_storable': True})
        order = self._order(mechanic_id=False)
        self._ready_to_finish(order)
        with self.assertRaises(UserError) as error:
            order.write({
                'mechanic_id': self.mechanic.id,
                'part_line_ids': [Command.create({'product_id': no_stock.id})],
                'state': 'done',
            })
        self.assertIn('Correa sin stock', str(error.exception))
        self.assertNotIn('mecánico', str(error.exception))
        self.assertEqual(order.state, 'ready')

        order.write({'mechanic_id': self.mechanic.id, 'state': 'done'})
        self.assertEqual(order.state, 'done', 'El mecánico cargado en el mismo guardado cuenta')
        self.assertTrue(order.invoice_id)

    def test_labor_fraction_invoiced_as_in_order(self):
        # 0:20 h a 100.000 la hora: la factura da lo mismo que la orden y el PDF.
        order = self._order(part_line_ids=[], labor_line_ids=[
            Command.create({'name': 'Ajuste', 'hours': 20 / 60, 'price_unit': 100000})])
        self._ready_to_finish(order)
        order.action_done()
        labor_line = order.invoice_id.invoice_line_ids.filtered(lambda line: line.product_id == self.labor_product)
        self.assertEqual(labor_line.quantity, order.labor_line_ids.hours)
        self.assertEqual(labor_line.price_subtotal, order.amount_labor)
        self.assertEqual(order.invoice_id.amount_untaxed, order.amount_total)

    def test_warranty_order_is_not_invoiced(self):
        order = self._order(service_type='warranty')
        self._ready_to_finish(order)
        order.action_done()
        self.assertEqual(order.state, 'done')
        self.assertFalse(order.invoice_id)
        self.assertEqual(self.part.with_context(location=self.warehouse.lot_stock_id.id).qty_available, 7,
                         'Los repuestos de garantía igual salen del stock')

    def test_reception_wizard(self):
        damage = self.env.ref('autoflow_management.damage_scratches')
        wizard = Form(self.env['autoflow.vehicle.reception.wizard'].with_context(default_vehicle_id=self.vehicle.id))
        self.assertEqual(wizard.odometer, 1000, 'Propone el último kilometraje del vehículo')
        wizard.partner_id = self.customer
        wizard.odometer = 1200
        wizard.fuel_level = 25
        wizard.damage_ids.add(damage)
        action = wizard.save().action_confirm()

        order = self.env['autoflow.workshop.order'].browse(action['res_id'])
        self.assertEqual((order.state, order.odometer, order.fuel_level, order.damage_ids),
                         ('received', 1200, 25, damage))
        self.assertEqual(self.vehicle.state, 'maintenance')

    def test_reception_wizard_rejects_lower_odometer(self):
        wizard = self.env['autoflow.vehicle.reception.wizard'].create({
            'vehicle_id': self.vehicle.id, 'partner_id': self.customer.id, 'odometer': 10,
        })
        with self.assertRaises(UserError):
            wizard.action_confirm()

    def test_workshop_parts_catalog(self):
        category = self.env.ref('autoflow_management.product_category_workshop')
        parts = self.env['product.product'].search([('categ_id', 'child_of', category.id)])
        self.assertGreaterEqual(len(parts), 25)
        self.assertTrue(all(part.is_storable and part.list_price > part.standard_price for part in parts),
                        'Todos los repuestos llevan stock y se venden por encima del costo')
        for xmlid in ('product_engine_oil', 'product_wheel_bearing_front', 'product_brake_disc'):
            self.assertIn(self.env.ref(f'autoflow_management.{xmlid}'), parts)
        self.assertTrue(all(part.image_128 for part in parts), 'Cada repuesto tiene su imagen')

    def test_part_line_offers_only_workshop_parts(self):
        chair = self.env['product.product'].create({'name': 'Silla de oficina', 'type': 'consu'})
        domain = self.env['autoflow.workshop.part.line']._domain_workshop_parts()
        offered = self.env['product.product'].search(domain)
        self.assertIn(self.env.ref('autoflow_management.product_brake_disc'), offered)
        self.assertNotIn(chair, offered, 'Un mueble no aparece al cargar repuestos')

    def test_report_renders(self):
        order = self._order()
        html = self.env['ir.actions.report']._render_qweb_html(
            'autoflow_management.report_workshop_order', order.ids)[0]
        self.assertIn(order.name.encode(), html)
        self.assertIn(b'Acta de entrega', html)
