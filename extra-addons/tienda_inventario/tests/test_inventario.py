# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestInventario(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.producto = cls.env['tienda.producto'].create({
            'name': 'Producto de prueba',
            'codigo': 'TEST-INV-001',
            'precio_venta': 10,
            'stock_minimo': 5,
        })

    def _asistente(self, **vals):
        return self.env['tienda.movimiento.wizard'].create({'producto_id': self.producto.id, **vals})

    def test_producto_nuevo_sin_stock(self):
        self.assertEqual(self.producto.stock, 0)
        self.assertTrue(self.producto.stock_bajo)

    def test_reponer_suma_stock(self):
        self._asistente(modo='reponer', cantidad=12, referencia='Factura 123').action_confirmar()
        movimiento = self.producto.movimiento_ids
        self.assertEqual(self.producto.stock, 12)
        self.assertFalse(self.producto.stock_bajo)
        self.assertEqual((movimiento.tipo, movimiento.cantidad, movimiento.saldo, movimiento.referencia),
                         ('reposicion', 12, 12, 'Factura 123'))

    def test_ajuste_deja_el_stock_contado(self):
        self._asistente(modo='reponer', cantidad=20).action_confirmar()
        self._asistente(modo='ajustar', stock_contado=17).action_confirmar()
        ajuste = self.producto.movimiento_ids.filtered(lambda m: m.tipo == 'ajuste')
        self.assertEqual(self.producto.stock, 17)
        self.assertEqual((ajuste.cantidad, ajuste.saldo), (-3, 17))

    def test_cantidades_invalidas(self):
        with self.assertRaises(UserError):
            self._asistente(modo='reponer', cantidad=0).action_confirmar()
        with self.assertRaises(UserError):
            self._asistente(modo='ajustar', stock_contado=-1).action_confirmar()
        with self.assertRaises(UserError):
            self._asistente(modo='ajustar', stock_contado=0).action_confirmar()

    def test_productos_precargados(self):
        arroz = self.env.ref('tienda_inventario.producto_arroz')
        inicial = arroz.movimiento_ids.filtered(lambda m: m.tipo == 'inicial')
        self.assertEqual(arroz.codigo, 'DES-001')
        self.assertEqual(inicial.cantidad, 40)
        self.assertEqual(arroz.iva, '5')

    def test_todo_en_guaranies(self):
        pyg = self.env.ref('base.PYG')
        self.assertEqual(self.env.ref('base.main_company').currency_id, pyg)
        self.assertEqual(self.producto.currency_id, pyg)
        precargados = self.env['tienda.producto'].search([('codigo', 'in', ['DES-001', 'BEB-001', 'HIG-002'])])
        self.assertEqual(precargados.currency_id, pyg)
