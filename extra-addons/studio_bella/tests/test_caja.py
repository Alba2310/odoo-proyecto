# -*- coding: utf-8 -*-
from datetime import timedelta

from psycopg2 import IntegrityError

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import new_test_user, tagged
from odoo.tools import mute_logger

from odoo.addons.studio_bella.tests.common import StudioBellaCommon


@tagged('post_install', '-at_install')
class TestCierreCaja(StudioBellaCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.hoy = fields.Date.context_today(cls.env.user)

    def _cierre(self, **valores):
        return self.env['bella.cierre.caja'].create({'fecha': self.hoy, **valores})

    def _venta_shampoo(self):
        return self.env['bella.venta'].create({
            'cliente_id': self.cliente.id,
            'linea_ids': [Command.create({'producto_id': self.shampoo.id, 'cantidad': 1})],
        })

    def test_totales_por_forma_de_pago_y_arqueo(self):
        self._cobrar(self._cita(), 'efectivo')  # 100
        self._cobrar(self._cita(inicio=self.lunes_10 + timedelta(hours=2), servicios=self.color), 'tarjeta')  # 200
        venta = self._venta_shampoo()
        self._cobrar(venta, 'transferencia')  # 50

        cierre = self._cierre(fondo_inicial=200, retiros=30)
        self.assertEqual(cierre.name, f'Caja del {self.hoy.strftime("%d/%m/%Y")}')
        self.assertEqual(
            (cierre.total_efectivo, cierre.total_tarjeta, cierre.total_transferencia, cierre.total_cobrado),
            (100, 200, 50, 350))
        self.assertEqual(cierre.cantidad_cobros, 3)
        self.assertEqual(len(cierre.cita_ids), 2)
        self.assertEqual(cierre.venta_ids, venta)

        # 200 de cambio + 100 cobrados en efectivo - 30 que se sacaron.
        self.assertEqual(cierre.efectivo_esperado, 270)
        cierre.efectivo_contado = 260
        self.assertEqual(cierre.diferencia, -10)
        self.assertEqual(cierre.resultado, 'falta')
        self.assertIn('Faltan', cierre.resultado_texto)
        self.assertEqual(cierre.queda_en_caja, 200)
        self.assertEqual(cierre.para_retirar, 60)

        cierre.action_cerrar()
        self.assertEqual(cierre.estado, 'cerrada')
        self.assertTrue(any('Faltan' in mensaje.body for mensaje in cierre.message_ids))

    def test_un_cobro_nuevo_suma_en_la_caja_abierta(self):
        cierre = self._cierre()
        self.assertEqual(cierre.total_cobrado, 0)
        self._cobrar(self._cita(), 'efectivo')
        self.assertEqual(cierre.total_efectivo, 100)
        self.assertEqual(cierre.cantidad_cobros, 1)

    def test_caja_cerrada_no_deja_cobrar_hasta_reabrirla(self):
        self._cobrar(self._cita(), 'efectivo')
        cierre = self._cierre(efectivo_contado=100)
        self.assertEqual(cierre.resultado, 'cuadra')
        cierre.action_cerrar()

        otra = self._cita(inicio=self.lunes_10 + timedelta(hours=2))
        with self.assertRaisesRegex(UserError, 'cerrada'):
            self._cobrar(otra, 'tarjeta')
        with self.assertRaises(UserError):
            cierre.retiros = 10
        cierre.nota = 'Se puede anotar algo con la caja cerrada.'

        recepcion = new_test_user(
            self.env, login='recepcion_caja', groups='studio_bella.group_bella_recepcion',
            company_id=self.company.id, company_ids=[Command.set(self.company.ids)],
        )
        with self.assertRaisesRegex(UserError, 'Administración'):
            cierre.with_user(recepcion).action_reabrir()

        cierre.action_reabrir()
        self._cobrar(otra, 'tarjeta')
        self.assertEqual(cierre.total_tarjeta, 100)

    def test_cerrar_pide_contar_el_efectivo(self):
        self._cobrar(self._cita(), 'efectivo')
        cierre = self._cierre()
        with self.assertRaisesRegex(UserError, 'Efectivo contado'):
            cierre.action_cerrar()
        cierre.write({'efectivo_contado': 100, 'queda_en_caja': 150})
        with self.assertRaisesRegex(UserError, 'cambio'):
            cierre.action_cerrar()

        manana = self._cierre(fecha=self.hoy + timedelta(days=1))
        with self.assertRaisesRegex(UserError, 'todavía no llegó'):
            manana.action_cerrar()

    def test_un_cierre_por_dia_y_el_cambio_pasa_al_dia_siguiente(self):
        ayer = self._cierre(fecha=self.hoy - timedelta(days=1), fondo_inicial=150)
        self.assertEqual(ayer.queda_en_caja, 150)
        ayer.queda_en_caja = 180
        hoy = self.env['bella.cierre.caja'].create({'fecha': self.hoy})
        self.assertEqual(hoy.fondo_inicial, 180)
        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError):
            self._cierre()

    def test_recepcion_cierra_la_caja(self):
        recepcion = new_test_user(
            self.env, login='recepcion_cierra', groups='studio_bella.group_bella_recepcion',
            company_id=self.company.id, company_ids=[Command.set(self.company.ids)],
        )
        self._cobrar(self._venta_shampoo(), 'efectivo')
        cierre = self.env['bella.cierre.caja'].with_user(recepcion).create({'fecha': self.hoy, 'efectivo_contado': 50})
        cierre.action_cerrar()
        self.assertEqual(cierre.estado, 'cerrada')
        self.assertEqual(cierre.responsable_id, recepcion)

    def test_comprobante_imprimible(self):
        self._cobrar(self._cita(), 'efectivo')
        cierre = self._cierre(efectivo_contado=100)
        html = self.env['ir.actions.report']._render_qweb_html('studio_bella.report_cierre_caja', cierre.ids)[0]
        self.assertIn('Arqueo del efectivo', str(html))
        self.assertIn(self.cliente.name, str(html))
