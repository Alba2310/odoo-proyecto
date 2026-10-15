# -*- coding: utf-8 -*-
from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestVentas(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Producto = cls.env['tienda.producto']
        cls.gaseosa = Producto.create({
            'name': 'Gaseosa de prueba', 'codigo': 'TEST-VTA-001', 'precio_venta': 11000, 'iva': '10',
        })
        cls.agua = Producto.create({
            'name': 'Agua de prueba', 'codigo': 'TEST-VTA-002', 'precio_venta': 4200, 'iva': '10',
        })
        cls.arroz = Producto.create({
            'name': 'Arroz de prueba', 'codigo': 'TEST-VTA-003', 'precio_venta': 21000, 'iva': '5',
        })
        cls.env['tienda.movimiento'].create([
            {'producto_id': cls.gaseosa.id, 'tipo': 'inicial', 'cantidad': 10},
            {'producto_id': cls.agua.id, 'tipo': 'inicial', 'cantidad': 5},
            {'producto_id': cls.arroz.id, 'tipo': 'inicial', 'cantidad': 10},
        ])
        cls.caja = cls.env['tienda.caja'].create({'monto_inicial': 50000})

    def _venta(self, *lineas, **valores):
        return self.env['tienda.venta'].create({
            'linea_ids': [Command.create(dict(producto_id=producto.id, cantidad=cantidad, **extra))
                          for producto, cantidad, extra in lineas],
            **valores,
        })

    def _cerrar_caja(self, efectivo_contado):
        asistente = self.env['tienda.caja.cierre.wizard'].create({
            'caja_id': self.caja.id, 'efectivo_contado': efectivo_contado,
        })
        return asistente, asistente.action_cerrar()

    # Ventas y stock

    def test_numeracion(self):
        venta = self._venta((self.gaseosa, 1, {}))
        self.assertTrue(venta.name.startswith('V'))
        self.assertNotEqual(venta.name, 'Nuevo')

    def test_confirmar_descuenta_stock(self):
        venta = self._venta((self.gaseosa, 3, {}), (self.agua, 2, {}))
        self.assertEqual(self.gaseosa.stock, 10, 'Una venta en borrador no mueve el stock')

        venta.action_confirmar()

        self.assertEqual(venta.estado, 'confirmada')
        self.assertEqual(venta.caja_id, self.caja)
        self.assertEqual((self.gaseosa.stock, self.agua.stock), (7, 3))
        movimiento = venta.movimiento_ids.filtered(lambda m: m.producto_id == self.gaseosa)
        self.assertEqual((movimiento.tipo, movimiento.cantidad, movimiento.saldo, movimiento.referencia),
                         ('venta', -3, 7, venta.name))

    def test_mismo_producto_en_dos_lineas(self):
        venta = self._venta((self.agua, 3, {}), (self.agua, 2, {}))
        venta.action_confirmar()
        self.assertEqual(self.agua.stock, 0)
        self.assertEqual(sorted(venta.movimiento_ids.mapped('saldo')), [0, 2])

    def test_stock_insuficiente(self):
        venta = self._venta((self.agua, 3, {}), (self.agua, 3, {}))
        with self.assertRaises(UserError):
            venta.action_confirmar()
        self.assertEqual(venta.estado, 'borrador')
        self.assertEqual(self.agua.stock, 5)

    def test_cancelar_devuelve_stock(self):
        venta = self._venta((self.gaseosa, 4, {}))
        venta.action_confirmar()
        venta.action_cancelar()
        self.assertEqual(venta.estado, 'cancelada')
        self.assertEqual(self.gaseosa.stock, 10)

        # Volver a borrador, reconfirmar y cancelar de nuevo no devuelve stock de más.
        venta.action_borrador()
        self.assertFalse(venta.caja_id)
        venta.action_confirmar()
        self.assertEqual(venta.caja_id, self.caja)
        self.assertEqual(self.gaseosa.stock, 6)
        venta.action_cancelar()
        self.assertEqual(self.gaseosa.stock, 10)

    def test_cancelar_borrador_no_mueve_stock(self):
        venta = self._venta((self.gaseosa, 4, {}))
        venta.action_cancelar()
        self.assertFalse(venta.movimiento_ids)
        self.assertEqual(self.gaseosa.stock, 10)

    def test_no_se_elimina_venta_confirmada(self):
        venta = self._venta((self.gaseosa, 1, {}))
        venta.action_confirmar()
        with self.assertRaises(UserError):
            venta.unlink()

    # Precios, IVA y pago

    def test_precio_descuento_e_iva(self):
        venta = self._venta((self.gaseosa, 2, {'descuento': 10}), (self.arroz, 1, {}))
        gaseosa, arroz = venta.linea_ids
        self.assertEqual((gaseosa.precio_unitario, gaseosa.iva, arroz.iva), (11000, '10', '5'))
        self.assertEqual((gaseosa.subtotal, gaseosa.importe_iva), (19800, 1800))  # 19.800 / 11
        self.assertEqual((arroz.subtotal, arroz.importe_iva), (21000, 1000))  # 21.000 / 21
        self.assertEqual((venta.subtotal, venta.descuento_total, venta.total), (43000, 2200, 40800))
        self.assertEqual((venta.iva_10, venta.iva_5), (1800, 1000))

    def test_iva_queda_fijo_en_la_venta(self):
        venta = self._venta((self.arroz, 1, {}))
        self.arroz.iva = '10'
        self.assertEqual(venta.linea_ids.iva, '5', 'Cambiar el IVA del producto no cambia ventas ya cargadas')

    def test_vuelto(self):
        venta = self._venta((self.agua, 1, {}), metodo_pago='efectivo', monto_recibido=10000)
        self.assertEqual(venta.vuelto, 5800)
        venta.action_confirmar()

        con_tarjeta = self._venta((self.agua, 1, {}), metodo_pago='tarjeta', monto_recibido=10000)
        self.assertEqual(con_tarjeta.vuelto, 0)

    def test_efectivo_insuficiente(self):
        venta = self._venta((self.agua, 1, {}), metodo_pago='efectivo', monto_recibido=4000)
        with self.assertRaises(UserError):
            venta.action_confirmar()
        self.assertEqual(venta.estado, 'borrador')

    # Caja

    def test_una_caja_abierta_por_usuario(self):
        with self.assertRaises(ValidationError):
            self.env['tienda.caja'].create({'monto_inicial': 0})

    def test_cierre_de_caja(self):
        self._venta((self.gaseosa, 1, {}), metodo_pago='efectivo').action_confirmar()
        self._venta((self.agua, 1, {}), metodo_pago='tarjeta').action_confirmar()
        self._venta((self.arroz, 1, {}), metodo_pago='transferencia').action_confirmar()
        anulada = self._venta((self.agua, 1, {}), metodo_pago='efectivo')
        anulada.action_confirmar()
        anulada.action_cancelar()

        caja = self.caja
        self.assertEqual(caja.cantidad_ventas, 3, 'La venta cancelada no cuenta')
        self.assertEqual((caja.total_efectivo, caja.total_tarjeta, caja.total_transferencia, caja.total_ventas),
                         (11000, 4200, 21000, 36200))
        self.assertEqual((caja.iva_10, caja.iva_5), (1000 + 382, 1000))
        self.assertEqual(caja.efectivo_esperado, 61000)  # 50.000 de fondo + 11.000 en efectivo

        asistente, accion = self._cerrar_caja(60000)
        self.assertEqual(asistente.diferencia, -1000)
        self.assertEqual(accion['type'], 'ir.actions.report', 'Al cerrar se descarga el resumen')
        self.assertEqual((caja.estado, caja.efectivo_contado, caja.diferencia), ('cerrada', 60000, -1000))
        self.assertTrue(caja.fecha_cierre)

        with self.assertRaises(UserError):
            caja.venta_ids.filtered(lambda v: v.estado == 'confirmada')[0].action_cancelar()

    def test_sin_caja_abierta_no_se_vende(self):
        self._cerrar_caja(50000)
        venta = self._venta((self.gaseosa, 1, {}))
        with self.assertRaises(UserError):
            venta.action_confirmar()
        self.assertEqual(self.gaseosa.stock, 10)

    # Tickets

    def test_ticket(self):
        venta = self._venta((self.gaseosa, 5, {'descuento': 10}), (self.agua, 1, {}),
                            metodo_pago='efectivo', monto_recibido=60000)
        venta.action_confirmar()
        html = self.env['ir.actions.report']._render_qweb_html(
            'tienda_ventas.ticket_venta', venta.ids)[0].decode()
        for texto in (venta.name, 'Gaseosa de prueba', 'Agua de prueba', 'Consumidor final', 'TOTAL',
                      'Efectivo', 'Vuelto', 'Liquidación del IVA'):
            self.assertIn(texto, html)
        self.assertNotIn('VENTA ANULADA', html)

        alto_dos_productos = venta._alto_ticket_mm()
        un_producto = self._venta((self.agua, 1, {}), metodo_pago='efectivo', monto_recibido=60000)
        un_producto.action_confirmar()
        self.assertGreater(alto_dos_productos, un_producto._alto_ticket_mm())

        venta.action_cancelar()
        html = self.env['ir.actions.report']._render_qweb_html(
            'tienda_ventas.ticket_venta', venta.ids)[0].decode()
        self.assertIn('VENTA ANULADA', html)
        self.assertGreater(venta._alto_ticket_mm(), alto_dos_productos, 'El sello de anulada ocupa lugar')

    def test_resumen_de_caja(self):
        self._venta((self.gaseosa, 1, {})).action_confirmar()
        resumen = lambda: self.env['ir.actions.report']._render_qweb_html(
            'tienda_ventas.ticket_cierre_caja', self.caja.ids)[0].decode()

        html = resumen()
        for texto in (self.caja.name, 'CIERRE DE CAJA', 'resumen parcial', 'Efectivo'):
            self.assertIn(texto, html)

        self._cerrar_caja(60000)
        html = resumen()
        self.assertNotIn('resumen parcial', html)
        self.assertIn('FALTANTE', html)
