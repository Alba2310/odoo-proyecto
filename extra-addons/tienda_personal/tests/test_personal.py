# -*- coding: utf-8 -*-
from datetime import datetime, time, timedelta

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.tienda_personal.models.comun import hoy


@tagged('post_install', '-at_install')
class TestPersonal(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.aregua = cls.env.ref('tienda_inventario.sucursal_aregua')
        cls.hoy = hoy()
        # Lunes de la semana pasada: una semana entera que ya terminó.
        cls.lunes = cls.hoy - timedelta(days=cls.hoy.weekday() + 7)
        cls.empleado = cls._nuevo_empleado('Empleado de prueba', control_desde=cls.lunes)

    @classmethod
    def _nuevo_empleado(cls, nombre, **valores):
        return cls.env['tienda.empleado'].create({
            'name': nombre, 'sucursal_id': cls.aregua.id, 'pago_hora': 10000, **valores})

    def _dia(self, numero):
        """Día de la semana pasada: 0 = lunes ... 6 = domingo."""
        return self.lunes + timedelta(days=numero)

    def _trabajo(self, fecha, horas, empleado=None):
        entrada = datetime.combine(fecha, time(11, 0))
        return self.env['tienda.asistencia'].create({
            'empleado_id': (empleado or self.empleado).id, 'fecha': fecha, 'estado': 'presente',
            'entrada': entrada, 'salida': entrada + timedelta(hours=horas) if horas else False,
        })

    def _ajuste(self, tipo, monto, motivo='Prueba'):
        return self.env['tienda.ajuste'].create({
            'empleado_id': self.empleado.id, 'tipo': tipo, 'monto': monto, 'motivo': motivo, 'fecha': self.hoy})

    def _panel(self):
        self.empleado.invalidate_recordset()
        return self.empleado

    # Horas y asistencia

    def test_pago_por_hora_trabajada(self):
        dia = self._trabajo(self._dia(0), 8.5)
        self.assertEqual((dia.horas, dia.pago_hora, dia.monto), (8.5, 10000, 85000))

        self.empleado.pago_hora = 12000
        self.assertEqual(dia.monto, 85000, 'Cambiar el pago por hora no cambia los días ya cargados')

    def test_marcar_entrada_y_salida(self):
        self.empleado.action_marcar_entrada()
        self.assertEqual(self._panel().estado_hoy, 'trabajando')
        with self.assertRaises(UserError):
            self.empleado.action_marcar_entrada()

        self.empleado.action_marcar_salida()
        self.assertEqual(self._panel().estado_hoy, 'salio')
        with self.assertRaises(UserError):
            self.empleado.action_marcar_salida()

    def test_salida_sin_entrada(self):
        with self.assertRaises(UserError):
            self.empleado.action_marcar_salida()

    # Faltas y reposos

    def test_el_sistema_marca_las_faltas(self):
        self._trabajo(self._dia(0), 8)
        faltas = self.env['tienda.asistencia']._marcar_faltas(hasta=self._dia(6))
        mias = faltas.filtered(lambda a: a.empleado_id == self.empleado)
        self.assertEqual(sorted(mias.mapped('fecha')), [self._dia(n) for n in range(1, 6)],
                         'Martes a sábado: el lunes vino y el domingo no trabaja')
        self.assertEqual(set(mias.mapped('estado')), {'falta'})
        self.assertTrue(all(mias.mapped('automatica')))

        otra_vez = self.env['tienda.asistencia']._marcar_faltas(hasta=self._dia(6))
        self.assertFalse(otra_vez.filtered(lambda a: a.empleado_id == self.empleado), 'No duplica')

    def test_no_marca_faltas_antes_de_controlar(self):
        nuevo = self._nuevo_empleado('Recién llegado', control_desde=self._dia(3))
        faltas = self.env['tienda.asistencia']._marcar_faltas(hasta=self._dia(6))
        self.assertEqual(sorted(faltas.filtered(lambda a: a.empleado_id == nuevo).mapped('fecha')),
                         [self._dia(3), self._dia(4), self._dia(5)])

    def test_reposo_no_es_falta(self):
        Reposo = self.env['tienda.reposo']
        Reposo.create({'empleado_id': self.empleado.id, 'desde': self._dia(1), 'hasta': self._dia(2),
                       'motivo': 'Gripe'})
        Asistencia = self.env['tienda.asistencia']
        Asistencia._marcar_faltas(hasta=self._dia(6))
        estado = lambda n: Asistencia.search([('empleado_id', '=', self.empleado.id),
                                              ('fecha', '=', self._dia(n))]).estado
        self.assertEqual([estado(n) for n in range(6)],
                         ['falta', 'reposo', 'reposo', 'falta', 'falta', 'falta'])

        # Un reposo cargado después convierte la falta en reposo; si se borra, vuelve a ser falta.
        tardio = Reposo.create({'empleado_id': self.empleado.id, 'desde': self._dia(3),
                                'hasta': self._dia(3), 'motivo': 'Certificado entregado tarde'})
        self.assertEqual(estado(3), 'reposo')
        tardio.unlink()
        self.assertEqual(estado(3), 'falta')

    def test_bono_segun_las_faltas_del_mes(self):
        self.assertTrue(self._panel().corresponde_bono)

        falta = self.env['tienda.asistencia'].create({
            'empleado_id': self.empleado.id, 'fecha': self.hoy, 'estado': 'falta'})
        empleado = self._panel()
        self.assertEqual((empleado.faltas_mes, empleado.corresponde_bono), (1, False))
        self.assertIn(empleado, self.env['tienda.empleado'].search([('corresponde_bono', '=', False)]))

        falta.estado = 'reposo'
        self.assertTrue(self._panel().corresponde_bono, 'El reposo no le quita el bono')

    # Pagos

    def test_pago(self):
        lunes = self._trabajo(self._dia(0), 8)
        self._trabajo(self._dia(1), 4)
        sin_salida = self._trabajo(self._dia(2), 0)
        self._ajuste('bono', 50000)
        self._ajuste('sancion', 10000)

        empleado = self._panel()
        self.assertEqual((empleado.a_pagar, empleado.dias_sin_salida), (160000, 1))
        self.assertIn(empleado, self.env['tienda.empleado'].search([('a_pagar', '>', 0)]))

        pago = self.env['tienda.pago'].browse(empleado.action_pagar()['res_id'])
        self.assertEqual((pago.dias, pago.horas, pago.monto_horas), (2, 12, 120000))
        self.assertEqual((pago.total_bonos, pago.total_sanciones, pago.total), (50000, 10000, 160000))
        self.assertNotIn(sin_salida, pago.asistencia_ids, 'Un día sin salida no se paga hasta corregirlo')

        accion = pago.action_confirmar()
        self.assertEqual(accion['type'], 'ir.actions.report', 'Al pagar se descarga el recibo')
        self.assertEqual(pago.estado, 'pagado')
        self.assertTrue(lunes.pagado)
        self.assertEqual(self._panel().a_pagar, 0)

        with self.assertRaises(UserError):
            lunes.salida = lunes.salida + timedelta(hours=1)
        with self.assertRaises(UserError):
            lunes.unlink()
        with self.assertRaises(UserError):
            self.empleado.action_pagar()

    def test_anular_pago(self):
        dia = self._trabajo(self._dia(0), 8)
        pago = self.env['tienda.pago'].browse(self.empleado.action_pagar()['res_id'])
        pago.action_confirmar()
        pago.action_anular()
        self.assertEqual(pago.estado, 'anulado')
        self.assertFalse(dia.pago_id)
        self.assertEqual(self._panel().a_pagar, 80000, 'Lo anulado vuelve a quedar pendiente')

    def test_sanciones_mayores_que_lo_trabajado(self):
        self._trabajo(self._dia(0), 1)
        self._ajuste('sancion', 100000)
        pago = self.env['tienda.pago'].browse(self.empleado.action_pagar()['res_id'])
        with self.assertRaises(UserError):
            pago.action_confirmar()

    def test_recibo(self):
        self._trabajo(self._dia(0), 8)
        self._ajuste('bono', 50000, 'Buen desempeño')
        pago = self.env['tienda.pago'].browse(self.empleado.action_pagar()['res_id'])
        pago.action_confirmar()
        html = self.env['ir.actions.report']._render_qweb_html('tienda_personal.recibo_pago', pago.ids)[0].decode()
        for texto in (pago.name, 'Empleado de prueba', 'RECIBO DE PAGO', 'Buen desempeño', 'Firma del empleado'):
            self.assertIn(texto, html)
