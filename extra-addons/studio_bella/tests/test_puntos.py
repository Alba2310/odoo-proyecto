# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import Form, tagged

from odoo.addons.studio_bella.tests.common import StudioBellaCommon


@tagged('post_install', '-at_install')
class TestPuntos(StudioBellaCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # 1 punto cada 10 pagados; cada punto vale 1 de descuento.
        cls.company.write({'bella_puntos_activo': True, 'bella_puntos_monto': 10, 'bella_puntos_valor': 1})
        cls.iva_5 = cls.env['account.tax'].create({
            'name': 'IVA 5 % de prueba',
            'amount': 5,
            'type_tax_use': 'sale',
            'price_include_override': 'tax_included',
        })
        cls.crema = cls.env['product.product'].create({
            'name': 'Crema de prueba', 'type': 'consu', 'is_storable': True, 'list_price': 20,
            'categ_id': cls.env.ref('studio_bella.categoria_productos').id,
            'taxes_id': [Command.set(cls.iva_5.ids)],
        })
        cls.env['stock.quant']._update_available_quantity(cls.crema, cls.stock, 5)

    def _regalar_puntos(self, puntos):
        self.env['bella.puntos'].create({'cliente_id': self.cliente.id, 'puntos': puntos, 'concepto': 'Regalo'})

    def _segunda_cita(self, **valores):
        return self._cita(inicio=self.lunes_10 + timedelta(hours=2), **valores)

    def test_gana_puntos_al_pagar(self):
        cita = self._cita()
        self._cobrar(cita)  # Corte 100
        self.assertEqual(self.cliente.bella_puntos, 10)
        self.assertEqual(self.cliente.bella_puntos_ids.concepto, f'Ganados en {cita.name}')
        self.assertEqual(self.cliente.bella_puntos_ids.factura_id, cita.factura_id)
        self.assertTrue(any('ganó 10 puntos' in mensaje.body for mensaje in cita.message_ids))

    def test_sin_puntos_con_el_programa_apagado_o_consumidor_final(self):
        self.company.bella_puntos_activo = False
        self._cobrar(self._cita())
        self.assertFalse(self.cliente.bella_puntos_ids)

        self.company.bella_puntos_activo = True
        venta = self.env['bella.venta'].create({
            'linea_ids': [Command.create({'producto_id': self.shampoo.id, 'cantidad': 1})],
        })
        self.assertEqual(venta.cliente_id, self.env.ref('studio_bella.cliente_consumidor_final'))
        self._cobrar(venta)
        self.assertFalse(self.env['bella.puntos'].search([('cliente_id', '=', venta.cliente_id.id)]))

    def test_usar_puntos_en_el_cobro(self):
        self._regalar_puntos(10)
        cita = self._segunda_cita(servicios=self.color,
                                  producto_ids=[Command.create({'producto_id': self.shampoo.id, 'cantidad': 1})])
        wizard = Form(self.env['bella.cobro.wizard'].with_context(default_cita_id=cita.id))
        self.assertEqual(wizard.puntos_disponibles, 10)
        self.assertEqual(wizard.puntos_maximos, 10)
        wizard.puntos_canje = 5
        wizard.monto_recibido = 250
        self.assertEqual(wizard.total_a_cobrar, 245)  # 200 + 50 - 5
        self.assertEqual(wizard.vuelto, 5)
        wizard.save().action_cobrar()

        factura = cita.factura_id
        self.assertEqual(factura.amount_total, 245)
        # Odoo redondea el IVA línea por línea: puede diferir un centavo por línea del cálculo sobre el total.
        self.assertAlmostEqual(factura.amount_tax, 245 / 11, delta=0.02)
        self.assertEqual(cita.monto_cobrado, 245)
        descuento = factura.invoice_line_ids.filtered(lambda linea: linea.price_unit < 0)
        self.assertEqual((descuento.name, descuento.price_total), ('Descuento por 5 puntos', -5))
        # 10 - 5 usados + 24 ganados con lo que pagó (245).
        self.assertEqual(self.cliente.bella_puntos, 29)

        # El cierre de caja suma lo que de verdad se cobró.
        cierre = self.env['bella.cierre.caja'].create({'fecha': factura.invoice_date})
        self.assertEqual(cierre.total_efectivo, 245)

    def test_descuento_repartido_entre_las_tasas_de_iva(self):
        self._regalar_puntos(12)
        cita = self._cita(producto_ids=[Command.create({'producto_id': self.crema.id, 'cantidad': 1})])
        cita._bella_cobrar('efectivo', puntos=12)  # Corte 100 con IVA 10 % + crema 20 con IVA 5 %

        factura = cita.factura_id
        self.assertEqual(factura.amount_total, 108)
        descuentos = factura.invoice_line_ids.filtered(lambda linea: linea.price_unit < 0)
        por_iva = {linea.tax_ids: linea.price_total for linea in descuentos}
        self.assertEqual(por_iva, {self.iva_10: -10, self.iva_5: -2})
        # IVA sobre lo cobrado: 90 con el 10 % y 18 con el 5 %.
        self.assertAlmostEqual(factura.amount_tax, 90 / 11 + 18 / 21, delta=0.02)

    def test_no_se_usan_mas_puntos_de_los_que_hay(self):
        self._regalar_puntos(3)
        cita = self._cita()
        with self.assertRaises(UserError):
            cita._bella_cobrar('efectivo', puntos=5)

        wizard = Form(self.env['bella.cobro.wizard'].with_context(default_cita_id=cita.id))
        wizard.puntos_canje = 4
        with self.assertRaises(UserError):
            wizard.save().action_cobrar()
        self.assertFalse(cita.factura_id)

    def test_cada_compania_tiene_sus_puntos(self):
        self._regalar_puntos(10)
        otra = self.env['res.company'].create({'name': 'Otra sucursal'})
        self.env['bella.puntos'].sudo().create({
            'company_id': otra.id, 'cliente_id': self.cliente.id, 'puntos': 50, 'concepto': 'En la otra sucursal',
        })
        self.assertEqual(self.cliente._bella_saldo_puntos(self.company), 10)
        self.assertEqual(self.cliente._bella_saldo_puntos(otra), 50)
        cita = self._cita()
        self.assertEqual(cita.cliente_puntos, 10)
        with self.assertRaises(UserError):
            cita._bella_cobrar('efectivo', puntos=20)

    def test_no_mas_descuento_que_el_total(self):
        self._regalar_puntos(500)
        cita = self._cita()  # 100
        wizard = Form(self.env['bella.cobro.wizard'].with_context(default_cita_id=cita.id))
        self.assertEqual(wizard.puntos_maximos, 100)
        with self.assertRaises(UserError):
            cita._bella_cobrar('efectivo', puntos=101)

        # Con todos los puntos que alcanzan, la factura queda en cero y no hay pago que registrar.
        cita._bella_cobrar('efectivo', puntos=100)
        self.assertEqual(cita.factura_id.amount_total, 0)
        self.assertEqual(self.cliente.bella_puntos, 400)
