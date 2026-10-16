# -*- coding: utf-8 -*-
from psycopg2 import IntegrityError

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestInventario(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.aregua = cls.env.ref('tienda_inventario.sucursal_aregua')
        cls.capiata = cls.env.ref('tienda_inventario.sucursal_capiata')
        cls.producto = cls.env['tienda.producto'].create({
            'name': 'Producto de prueba',
            'codigo': 'TEST-INV-001',
            'sucursal_id': cls.aregua.id,
            'precio_venta': 10,
            'stock_minimo': 5,
        })

    def _asistente(self, **vals):
        return self.env['tienda.movimiento.wizard'].create({'producto_id': self.producto.id, **vals})

    def _stock(self):
        return self.producto.stock_despensa, self.producto.stock_deposito, self.producto.stock

    def test_producto_nuevo_sin_stock(self):
        self.assertEqual(self._stock(), (0, 0, 0))
        self.assertTrue(self.producto.stock_bajo)

    def test_reponer_entra_al_deposito(self):
        asistente = self._asistente(modo='reponer', cantidad=12, referencia='Factura 123')
        self.assertEqual(asistente.ubicacion, 'deposito')
        asistente.action_confirmar()
        movimiento = self.producto.movimiento_ids
        self.assertEqual(self._stock(), (0, 12, 12))
        self.assertFalse(self.producto.stock_bajo)
        self.assertEqual((movimiento.tipo, movimiento.ubicacion, movimiento.cantidad, movimiento.saldo),
                         ('reposicion', 'deposito', 12, 12))

    def test_reponer_directo_a_la_despensa(self):
        self._asistente(modo='reponer', ubicacion='despensa', cantidad=5).action_confirmar()
        self.assertEqual(self._stock(), (5, 0, 5))

    def test_pasar_del_deposito_a_la_despensa(self):
        self._asistente(modo='reponer', cantidad=20).action_confirmar()
        asistente = self._asistente(modo='transferir', cantidad=8)
        self.assertEqual((asistente.ubicacion, asistente.destino), ('deposito', 'Despensa'))
        asistente.action_confirmar()

        self.assertEqual(self._stock(), (8, 12, 20), 'Pasar mercadería no cambia el total')
        pasos = self.producto.movimiento_ids.filtered(lambda m: m.tipo == 'transferencia')
        self.assertEqual(sorted(pasos.mapped(lambda m: (m.ubicacion, m.cantidad, m.saldo))),
                         [('deposito', -8, 12), ('despensa', 8, 8)])

        with self.assertRaises(UserError):
            self._asistente(modo='transferir', cantidad=13).action_confirmar()

    def test_ajuste_deja_el_stock_contado(self):
        self._asistente(modo='reponer', cantidad=20).action_confirmar()
        self._asistente(modo='ajustar', ubicacion='deposito', stock_contado=17).action_confirmar()
        ajuste = self.producto.movimiento_ids.filtered(lambda m: m.tipo == 'ajuste')
        self.assertEqual(self._stock(), (0, 17, 17))
        self.assertEqual((ajuste.cantidad, ajuste.saldo), (-3, 17))

    def test_cantidades_invalidas(self):
        with self.assertRaises(UserError):
            self._asistente(modo='reponer', cantidad=0).action_confirmar()
        with self.assertRaises(UserError):
            self._asistente(modo='transferir', cantidad=0).action_confirmar()
        with self.assertRaises(UserError):
            self._asistente(modo='ajustar', stock_contado=-1).action_confirmar()
        with self.assertRaises(UserError):
            self._asistente(modo='ajustar', stock_contado=0).action_confirmar()

    def test_codigo_unico_por_sucursal(self):
        Producto = self.env['tienda.producto']
        otro = Producto.create({'name': 'Mismo código', 'codigo': 'TEST-INV-001',
                                'sucursal_id': self.capiata.id, 'precio_venta': 10})
        self.assertTrue(otro, 'El mismo código puede usarse en otra sucursal')
        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError):
            Producto.create({'name': 'Repetido', 'codigo': 'TEST-INV-001',
                             'sucursal_id': self.aregua.id, 'precio_venta': 10})
            Producto.flush_model()

    def test_productos_precargados(self):
        arroz = self.env.ref('tienda_inventario.producto_arroz')
        inicial = arroz.movimiento_ids.filtered(lambda m: m.tipo == 'inicial')
        self.assertEqual((arroz.codigo, arroz.sucursal_id, arroz.iva), ('DES-001', self.aregua, '5'))
        self.assertEqual(inicial.cantidad, 40)

        huevos = self.env.ref('tienda_inventario.cap_huevos_maple')
        self.assertEqual((huevos.sucursal_id, huevos.unidad), (self.capiata, 'caja'))
        inicial = huevos.movimiento_ids.filtered(lambda m: m.tipo == 'inicial')
        self.assertEqual((inicial.ubicacion, inicial.cantidad), ('deposito', 10))
        self.assertEqual(self.env.ref('tienda_inventario.cap_yerba_pajarito').display_name,
                         'Yerba mate 1 kg (Pajarito)')

    def test_todo_en_guaranies(self):
        pyg = self.env.ref('base.PYG')
        self.assertEqual(self.env.ref('base.main_company').currency_id, pyg)
        self.assertEqual(self.producto.currency_id, pyg)
        precargados = self.env['tienda.producto'].search([('codigo', 'in', ['DES-001', 'BEB-001', 'C-DES-001'])])
        self.assertEqual(precargados.currency_id, pyg)
