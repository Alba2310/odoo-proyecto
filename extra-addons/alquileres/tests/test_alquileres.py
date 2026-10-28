# -*- coding: utf-8 -*-
from datetime import date, timedelta
from urllib.parse import unquote

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo.addons.alquileres.models.contrato import DIAS_ANTICIPACION
from odoo.addons.alquileres.models.utiles import en_letras, guaranies, numero_whatsapp


class AlquileresCommon(TransactionCase):
    """Un edificio con dos departamentos y un inquilino."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.groups_id += cls.env.ref('alquileres.group_alquiler_admin')
        cls.hoy = fields.Date.context_today(cls.env.user)
        cls.edificio = cls.env['alquiler.propiedad'].create({
            'name': 'Edificio de prueba',
            'tipo': 'edificio',
            'ciudad': 'Ypacaraí',
            'unidad_ids': [Command.create({'name': 'Depto 1', 'piso': 1, 'alquiler_sugerido': 1300000}),
                           Command.create({'name': 'Depto 2', 'piso': 1})],
        })
        cls.depto1, cls.depto2 = cls.edificio.unidad_ids
        cls.inquilino = cls.env['res.partner'].create({'name': 'Juan Pérez', 'phone': '0981 123 456'})

    def _contrato(self, **valores):
        return self.env['alquiler.contrato'].create({
            'unidad_id': self.depto1.id,
            'inquilino_id': self.inquilino.id,
            'monto': 1500000,
            'dia_pago': 5,
            'fecha_inicio': self.hoy - timedelta(days=60),
            **valores,
        })

    def _pagar(self, cuota, monto=None, **valores):
        return self.env['alquiler.pago'].create({'cuota_id': cuota.id, 'monto': monto or cuota.saldo, **valores})


@tagged('post_install', '-at_install')
class TestAlquileres(AlquileresCommon):

    def test_casa_crea_su_unidad_y_nombres(self):
        casa = self.env['alquiler.propiedad'].create({'name': 'Casa de prueba', 'tipo': 'casa', 'ciudad': 'Caacupé'})
        self.assertEqual(casa.unidad_ids.name, 'Casa')
        self.assertEqual(casa.unidad_ids.display_name, 'Casa de prueba')
        self.assertEqual(self.depto1.display_name, 'Edificio de prueba · Depto 1')

    def test_cuotas_de_cada_mes(self):
        # Empieza el 20 de enero y paga los 5: la primera vence el día que empieza, después cada 5.
        contrato = self._contrato(fecha_inicio=date(2025, 1, 20), fecha_fin=date(2025, 5, 19))
        contrato.action_activar()
        self.assertEqual(contrato.cuota_ids.sorted('fecha_vencimiento').mapped('fecha_vencimiento'),
                         [date(2025, 1, 20), date(2025, 2, 5), date(2025, 3, 5), date(2025, 4, 5), date(2025, 5, 5)])
        self.assertEqual(contrato.cuota_ids.sorted('periodo')[0].name, 'Enero 2025')
        self.assertEqual(set(contrato.cuota_ids.mapped('monto')), {1500000})
        # Volver a generar no duplica.
        contrato._generar_cuotas()
        self.assertEqual(len(contrato.cuota_ids), 5)

    def test_dia_31_en_meses_cortos(self):
        contrato = self._contrato(dia_pago=31, fecha_inicio=date(2024, 1, 31), fecha_fin=date(2024, 4, 30))
        contrato.action_activar()
        self.assertEqual(contrato.cuota_ids.sorted('fecha_vencimiento').mapped('fecha_vencimiento'),
                         [date(2024, 1, 31), date(2024, 2, 29), date(2024, 3, 31), date(2024, 4, 30)])

    def test_cuotas_hasta_unos_dias_antes_de_vencer(self):
        contrato = self._contrato(fecha_inicio=self.hoy - timedelta(days=100), dia_pago=self.hoy.day)
        contrato.action_activar()
        limite = self.hoy + timedelta(days=DIAS_ANTICIPACION)
        self.assertTrue(all(vence <= limite for vence in contrato.cuota_ids.mapped('fecha_vencimiento')))
        self.assertIn(self.hoy, contrato.cuota_ids.mapped('fecha_vencimiento'))
        self.assertEqual(contrato.proximo_vencimiento, self.hoy)  # la de hoy todavía no está atrasada
        # El cron crea las que van venciendo.
        cuota_hoy = contrato.cuota_ids.filtered(lambda c: c.fecha_vencimiento == self.hoy)
        cuota_hoy.unlink()
        self.env['alquiler.contrato']._cron_generar_cuotas()
        self.assertIn(self.hoy, contrato.cuota_ids.mapped('fecha_vencimiento'))

    def test_dia_de_pago_propuesto(self):
        contrato = self.env['alquiler.contrato'].create({
            'unidad_id': self.depto1.id, 'inquilino_id': self.inquilino.id, 'monto': 1500000,
            'fecha_inicio': date(2025, 3, 12),
        })
        self.assertEqual(contrato.dia_pago, 12)

    def test_pagos_parciales_y_total(self):
        contrato = self._contrato()
        contrato.action_activar()
        cuota = contrato.cuota_ids.sorted('fecha_vencimiento')[0]
        self.assertEqual(cuota.estado, 'pendiente')
        self.assertTrue(cuota.atrasada)
        self.assertEqual(contrato.deuda, sum(contrato.cuota_ids.filtered('atrasada').mapped('monto')))

        primero = self._pagar(cuota, 500000, fecha=self.hoy - timedelta(days=1))
        self.assertTrue(primero.name.startswith('REC/'))
        self.assertEqual((cuota.estado, cuota.pagado, cuota.saldo), ('parcial', 500000, 1000000))
        segundo = self._pagar(cuota, medio='transferencia')
        self.assertEqual((cuota.estado, cuota.saldo, cuota.fecha_pago), ('pagada', 0, self.hoy))
        self.assertFalse(cuota.atrasada)
        self.assertEqual(primero._saldo_despues(), 1000000)
        self.assertEqual(segundo._saldo_despues(), 0)
        with self.assertRaises(ValidationError):
            self._pagar(cuota, 1)

    def test_no_se_paga_de_mas(self):
        contrato = self._contrato()
        contrato.action_activar()
        cuota = contrato.cuota_ids[0]
        with self.assertRaises(ValidationError):
            self._pagar(cuota, cuota.monto + 1)

    def test_unidad_libre_o_alquilada(self):
        contrato = self._contrato()
        self.assertEqual(self.depto1.estado, 'libre')
        contrato.action_activar()
        self.assertEqual((self.depto1.estado, self.depto1.inquilino_id), ('alquilada', self.inquilino))
        self.assertTrue(self.inquilino.alquiler_es_inquilino)
        self.assertEqual(self.edificio.ocupacion, '1 de 2 alquiladas')
        self.assertEqual(self.edificio.alquiler_mensual, 1500000)
        otro = self._contrato(inquilino_id=self.env['res.partner'].create({'name': 'Otro inquilino'}).id)
        with self.assertRaises(ValidationError):
            otro.action_activar()
        contrato._terminar()
        self.assertEqual((contrato.estado, self.depto1.estado), ('terminado', 'libre'))
        otro.action_activar()
        self.assertEqual(self.depto1.inquilino_id.name, 'Otro inquilino')

    def test_terminar_borra_las_cuotas_futuras_sin_pagar(self):
        en_cinco_dias = self.hoy + timedelta(days=5)
        contrato = self._contrato(dia_pago=en_cinco_dias.day)
        contrato.action_activar()
        futura = contrato.cuota_ids.filtered(lambda c: c.fecha_vencimiento == en_cinco_dias)
        self.assertTrue(futura)
        pagada = contrato.cuota_ids.sorted('fecha_vencimiento')[0]
        self._pagar(pagada)
        contrato._terminar()
        self.assertEqual(contrato.fecha_fin, self.hoy)
        self.assertFalse(futura.exists())
        self.assertTrue(pagada.exists())
        with self.assertRaises(UserError):
            contrato.unlink()

    def test_color_en_el_tablero(self):
        self.assertEqual((self.depto1.color, self.depto1.situacion), (0, 'Libre'))
        contrato = self._contrato()
        contrato.action_activar()
        self.depto1.invalidate_recordset(['color', 'situacion'])
        self.assertEqual(self.depto1.color, 1)
        self.assertEqual(self.depto1.situacion, f'Debe {guaranies(contrato.deuda)}')
        for cuota in contrato.cuota_ids.filtered('atrasada'):
            self._pagar(cuota)
        self.depto1.invalidate_recordset(['color', 'situacion'])
        self.assertIn(self.depto1.color, (3, 10))

    def test_avisos_de_pago(self):
        contrato = self._contrato(fecha_inicio=date(2025, 1, 5), fecha_fin=date(2025, 1, 31))
        contrato.action_activar()
        cuota = contrato.cuota_ids
        vence = date(2025, 1, 5)
        self.assertEqual(cuota.proximo_aviso, vence - timedelta(days=3))
        cuota._registrar_aviso(vence - timedelta(days=3))
        self.assertEqual(cuota.proximo_aviso, vence)
        cuota._registrar_aviso(vence)
        self.assertEqual(cuota.proximo_aviso, vence + timedelta(days=3))
        cuota._registrar_aviso(vence + timedelta(days=4))
        self.assertEqual((cuota.proximo_aviso, cuota.avisos_enviados), (vence + timedelta(days=7), 3))

        self.assertIn('el 5 de enero vence el alquiler de enero de 2025', cuota._texto_whatsapp(date(2025, 1, 2)))
        self.assertIn('hoy vence', cuota._texto_whatsapp(vence))
        atrasado = cuota._texto_whatsapp(date(2025, 1, 9))
        self.assertIn('venció el 5 de enero y figura pendiente: Gs. 1.500.000', atrasado)
        self.assertTrue(atrasado.startswith('¡Hola Juan!'))

    def test_boton_de_whatsapp(self):
        contrato = self._contrato()
        contrato.action_activar()
        cuota = contrato.cuota_ids.sorted('fecha_vencimiento')[0]
        accion = cuota.action_whatsapp()
        self.assertTrue(accion['url'].startswith('https://wa.me/595981123456?text='))
        self.assertIn('Edificio de prueba · Depto 1', unquote(accion['url']))
        self.assertEqual((cuota.ultimo_aviso, cuota.avisos_enviados), (self.hoy, 1))
        self.assertTrue(contrato.message_ids.filtered(lambda m: 'Aviso de pago por WhatsApp' in m.body))

        self.inquilino.phone = False
        with self.assertRaises(UserError):
            cuota.action_whatsapp()
        self.inquilino.phone = '0981 123 456'
        self._pagar(cuota)
        with self.assertRaises(UserError):
            cuota.action_whatsapp()

    def test_numero_de_whatsapp(self):
        self.assertEqual(numero_whatsapp('0981 234 567'), '595981234567')
        self.assertEqual(numero_whatsapp('+54 9 11 1234-5678'), '5491112345678')
        self.assertEqual(numero_whatsapp('595981234567'), '595981234567')
        self.assertEqual(numero_whatsapp(''), '')

    def test_recibo(self):
        self.assertEqual(en_letras(1000000), 'un millón de guaraníes')
        self.assertEqual(en_letras(1500000), 'un millón quinientos mil guaraníes')
        contrato = self._contrato()
        contrato.action_activar()
        cuota = contrato.cuota_ids.sorted('fecha_vencimiento')[0]
        pago = self._pagar(cuota, 1000000)
        html = self.env['ir.actions.report']._render_qweb_html('alquileres.report_recibo', pago.ids)[0].decode()
        self.assertIn('un millón de guaraníes', html)
        self.assertIn('Juan Pérez', html)
        self.assertIn('Gs. 500.000', html)  # lo que queda de ese mes
        self.assertIn('Recibimos tu pago de Gs. 1.000.000', unquote(pago.action_whatsapp()['url']))

    def test_permisos_del_encargado(self):
        contrato = self._contrato()
        contrato.action_activar()
        cuota = contrato.cuota_ids.sorted('fecha_vencimiento')[0]
        encargado = new_test_user(self.env, login='encargado_alquileres',
                                  groups='base.group_user,alquileres.group_alquiler_encargado')
        cuota_encargado = cuota.with_user(encargado)
        cuota_encargado.action_whatsapp()
        self.env['alquiler.pago'].with_user(encargado).create({'cuota_id': cuota.id, 'monto': cuota.saldo})
        self.assertEqual(cuota.estado, 'pagada')
        with self.assertRaises(AccessError):
            self.env['alquiler.contrato'].with_user(encargado).create({
                'unidad_id': self.depto2.id, 'inquilino_id': self.inquilino.id, 'monto': 1000000,
            })
