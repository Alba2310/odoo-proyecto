# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.cuenta_corriente.models import res_currency_rate
from odoo.addons.cuenta_corriente.models.account_move_line import DOMINIO_CUENTA_CORRIENTE


@tagged('post_install', '-at_install')
class TestCuentaCorriente(AccountTestInvoicingCommon):
    """Una empresa en guaraníes con el dólar a 7.300 Gs desde el 1 de octubre y a 7.400 Gs desde el 15."""
    country_code = 'PY'

    @classmethod
    def setup_independent_company(cls, **kwargs):
        cls._enable_currency('PYG')
        return super().setup_independent_company(**kwargs)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.guaranies = cls.env.company.currency_id
        cls.dolar = cls.setup_other_currency('USD', rates=[('2026-10-01', 1 / 7300), ('2026-10-15', 1 / 7400)])
        cls.cliente = cls.env['res.partner'].create({'name': 'Cliente de prueba'})

    def _factura(self, fecha, monto, moneda, tipo='out_invoice'):
        return self._create_invoice_one_line(
            price_unit=monto, tax_ids=self.env['account.tax'], move_type=tipo, invoice_date=fecha,
            currency_id=moneda, partner_id=self.cliente, post=True)

    def _cobro(self, factura, fecha, moneda, monto=None):
        """Sin monto se cobra todo lo que falta, pasado a la moneda del cobro con la cotización de ese día."""
        valores = {'payment_date': fecha, 'currency_id': moneda.id}
        if monto:
            valores['amount'] = monto
        return self._register_payment(factura, **valores)

    def _movimientos(self):
        return self.env['account.move.line'].search(
            [('partner_id', '=', self.cliente.id), *DOMINIO_CUENTA_CORRIENTE], order='date, id')

    def _totales(self):
        movimientos = self._movimientos()
        return {campo: sum(movimientos.mapped(campo)) for campo in ('debit', 'credit', 'debe_usd', 'haber_usd')}

    def test_factura_en_dolares_pasa_a_guaranies(self):
        self._factura('2026-10-05', 1000, self.dolar)
        self.assertRecordValues(self._movimientos(), [
            {'cotizacion': 7300, 'debit': 7_300_000, 'credit': 0, 'debe_usd': 1000, 'haber_usd': 0},
        ])
        self.assertEqual(self.cliente.saldo_usd, 1000)
        self.assertEqual(self.cliente.saldo_gs, 7_300_000)

    def test_factura_en_guaranies_pasa_a_dolares(self):
        self._factura('2026-10-05', 730_000, self.guaranies)
        self.assertRecordValues(self._movimientos(), [
            {'cotizacion': 7300, 'debit': 730_000, 'credit': 0, 'debe_usd': 100, 'haber_usd': 0},
        ])

    def test_nota_de_credito_va_al_haber(self):
        self._factura('2026-10-05', 100, self.dolar, tipo='out_refund')
        self.assertRecordValues(self._movimientos(), [
            {'cotizacion': 7300, 'debit': 0, 'credit': 730_000, 'debe_usd': 0, 'haber_usd': 100},
        ])

    def test_cobro_en_dolares_con_otra_cotizacion(self):
        """El cobro va a 7.400 y la factura a 7.300: Odoo agrega la diferencia de cambio, que va solo en guaraníes,
        y la cuenta queda en cero en las dos monedas."""
        factura = self._factura('2026-10-05', 1000, self.dolar)
        self._cobro(factura, '2026-10-20', self.dolar)
        self.assertRecordValues(self._movimientos(), [
            {'cotizacion': 7300, 'debit': 7_300_000, 'credit': 0, 'debe_usd': 1000, 'haber_usd': 0},
            {'cotizacion': 7400, 'debit': 0, 'credit': 7_400_000, 'debe_usd': 0, 'haber_usd': 1000},
            {'cotizacion': 0, 'debit': 100_000, 'credit': 0, 'debe_usd': 0, 'haber_usd': 0},
        ])
        self.assertEqual(self._totales(), {
            'debit': 7_400_000, 'credit': 7_400_000, 'debe_usd': 1000, 'haber_usd': 1000,
        })
        self.assertEqual((self.cliente.saldo_gs, self.cliente.saldo_usd), (0, 0))

    def test_deuda_en_dolares_pagada_con_guaranies(self):
        """Los guaraníes del cobro pasan a dólares con la cotización de ese día; la diferencia de cambio (ahora en
        guaraníes) tampoco va en dólares."""
        factura = self._factura('2026-10-05', 1000, self.dolar)
        self._cobro(factura, '2026-10-20', self.guaranies)
        self.assertEqual(factura.payment_state, 'paid')
        self.assertRecordValues(self._movimientos(), [
            {'cotizacion': 7300, 'debit': 7_300_000, 'credit': 0, 'debe_usd': 1000, 'haber_usd': 0},
            {'cotizacion': 7400, 'debit': 0, 'credit': 7_400_000, 'debe_usd': 0, 'haber_usd': 1000},
            {'cotizacion': 0, 'debit': 100_000, 'credit': 0, 'debe_usd': 0, 'haber_usd': 0},
        ])
        self.assertEqual((self.cliente.saldo_gs, self.cliente.saldo_usd), (0, 0))

    def test_cobro_parcial(self):
        """Lo que falta cobrar queda a la cotización de la factura."""
        factura = self._factura('2026-10-05', 1000, self.dolar)
        self._cobro(factura, '2026-10-20', self.dolar, 400)
        self.assertEqual(self.cliente.saldo_usd, 600)
        self.assertEqual(self.cliente.saldo_gs, 600 * 7300)

    def test_saldo_de_un_contacto_de_la_empresa(self):
        self._factura('2026-10-05', 1000, self.dolar)
        contacto = self.env['res.partner'].create({'name': 'Contacto', 'parent_id': self.cliente.id})
        self.assertEqual(contacto.saldo_usd, 1000)

    def test_boton_abre_la_cuenta_del_cliente(self):
        accion = self.cliente.action_ver_cuenta_corriente()
        self.assertEqual(accion['res_model'], 'account.move.line')
        self.assertEqual(accion['context'], {'search_default_partner_id': self.cliente.id})

    def test_tipo_detalle_y_saldo_de_cada_movimiento(self):
        factura = self._factura('2026-10-05', 1000, self.dolar)
        devolucion = self._factura('2026-10-06', 100, self.dolar, tipo='out_refund')
        self._cobro(factura, '2026-10-20', self.dolar, 400)
        movimientos = self._movimientos()
        self.assertRecordValues(movimientos, [
            {'tipo_movimiento': 'factura', 'moneda_texto': 'Dólares', 'saldo_gs': 7_300_000, 'saldo_usd': 1000},
            {'tipo_movimiento': 'nota_credito', 'moneda_texto': 'Dólares', 'saldo_gs': 6_570_000, 'saldo_usd': 900},
            {'tipo_movimiento': 'cobro', 'moneda_texto': 'Dólares', 'saldo_gs': 3_610_000, 'saldo_usd': 500},
            {'tipo_movimiento': 'ajuste', 'moneda_texto': 'Guaraníes', 'saldo_gs': 3_650_000, 'saldo_usd': 500},
        ])
        self.assertEqual(movimientos[0].detalle, f'Factura {factura.name}')
        self.assertEqual(movimientos[1].detalle, f'Nota de crédito {devolucion.name}')
        self.assertTrue(movimientos[2].detalle.startswith(f'Cobro de la factura {factura.name} · '))
        self.assertEqual(movimientos[3].detalle, 'Ajuste por cambio de cotización del dólar')

    def test_el_saldo_cuenta_lo_anterior_aunque_se_vea_un_solo_mes(self):
        self._factura('2026-10-02', 1000, self.dolar)
        self._factura('2026-10-16', 200, self.dolar)
        segunda_quincena = self._movimientos().filtered(lambda linea: linea.date.day > 15)
        self.assertEqual((segunda_quincena.saldo_gs, segunda_quincena.saldo_usd), (8_780_000, 1200))

    def test_clientes_con_saldo_pendiente(self):
        sin_deuda = self.env['res.partner'].create({'name': 'Cliente al día'})
        self._factura('2026-10-05', 1000, self.dolar)
        con_saldo = self.env['res.partner'].search([('con_saldo', '=', True)])
        self.assertIn(self.cliente, con_saldo)
        self.assertNotIn(sin_deuda, con_saldo)
        self.assertIn(sin_deuda, self.env['res.partner'].search([('con_saldo', '=', False)]))

    def test_extracto_con_saldo_anterior(self):
        factura = self._factura('2026-10-05', 1000, self.dolar)
        self._cobro(factura, '2026-10-20', self.dolar, 400)
        extracto = self.cliente._extracto_cuenta_corriente(
            fields.Date.to_date('2026-10-10'), fields.Date.to_date('2026-10-31'))
        self.assertEqual((extracto['anterior_gs'], extracto['anterior_usd']), (7_300_000, 1000))
        self.assertEqual(extracto['movimientos'].mapped('tipo_movimiento'), ['cobro', 'ajuste'])
        self.assertEqual((extracto['saldo_gs'], extracto['saldo_usd']), (600 * 7300, 600))

    def test_extracto_en_pdf(self):
        # Sin diseño elegido, Odoo pide configurarlo antes de imprimir por primera vez.
        self.env.company.external_report_layout_id = self.env.ref('web.external_layout_standard')
        self._factura('2026-10-05', 1000, self.dolar)
        asistente = self.env['cuenta.corriente.extracto'].create({
            'partner_id': self.cliente.id, 'fecha_desde': '2026-10-01', 'fecha_hasta': '2026-10-31',
        })
        accion = asistente.action_descargar_pdf()
        self.assertEqual(accion['report_name'], 'cuenta_corriente.reporte_extracto')
        # Como la pantalla: con data, pide el PDF sin los ids (getReportUrl de web).
        html, _tipo = self.env['ir.actions.report'].with_context(lang='es_PY')._render_qweb_html(
            'cuenta_corriente.action_report_extracto', None, data=accion['data'])
        html = html.decode()
        self.assertIn('Extracto de cuenta corriente', html)
        self.assertIn('Cliente de prueba', html)
        self.assertIn('7.300.000', html)
        self.assertIn('1.000,00', html)

    def test_factura_en_dolares_muestra_los_guaranies(self):
        factura = self._factura('2026-10-05', 1000, self.dolar)
        self.assertEqual(factura._montos_en_dos_monedas(), {
            'total_gs': 7_300_000, 'total_usd': 1000, 'cotizacion': 7300,
            'fecha': fields.Date.to_date('2026-10-05'),
        })
        self._cobro(factura, '2026-10-20', self.dolar, 400)
        montos = factura._montos_en_dos_monedas()
        self.assertEqual((montos['saldo_gs'], montos['saldo_usd']), (600 * 7300, 600))

    def test_factura_en_guaranies_muestra_los_dolares(self):
        factura = self._factura('2026-10-05', 730_000, self.guaranies)
        montos = factura._montos_en_dos_monedas()
        self.assertEqual((montos['total_gs'], montos['total_usd'], montos['cotizacion']), (730_000, 100, 7300))

    def test_factura_y_recibo_en_pdf_con_las_dos_monedas(self):
        factura = self._factura('2026-10-05', 1000, self.dolar)
        pago = self._cobro(factura, '2026-10-20', self.guaranies)
        Reporte = self.env['ir.actions.report'].with_context(lang='es_PY')
        html_factura = Reporte._render_qweb_html('account.account_invoices', factura.ids)[0].decode()
        self.assertIn('name="dos_monedas"', html_factura)
        self.assertIn('7.300.000', html_factura)
        self.assertIn('7.300,00</span> Gs', html_factura)
        html_recibo = Reporte._render_qweb_html('account.action_report_payment_receipt', pago.ids)[0].decode()
        self.assertIn('Monto recibido', html_recibo)
        self.assertIn('7.400.000', html_recibo)

    def test_extracto_sin_movimientos_avisa_en_vez_de_bajar_un_pdf_vacio(self):
        self._factura('2026-10-05', 1000, self.dolar)
        asistente = self.env['cuenta.corriente.extracto'].with_context(lang='es_PY').create({
            'partner_id': self.cliente.id, 'fecha_desde': '2026-10-10', 'fecha_hasta': '2026-10-31',
        })
        with self.assertRaises(UserError) as aviso:
            asistente.action_descargar_pdf()
        mensaje = str(aviso.exception)
        self.assertIn('Cliente de prueba no tiene movimientos entre el 10/10/2026 y el 31/10/2026', mensaje)
        self.assertIn('Gs 7.300.000 · USD 1.000,00', mensaje)

        nuevo = self.env['res.partner'].create({'name': 'Cliente nuevo'})
        asistente.partner_id = nuevo
        with self.assertRaises(UserError) as aviso:
            asistente.action_descargar_pdf()
        self.assertNotIn('Su saldo', str(aviso.exception))

    def test_extracto_empieza_en_el_primer_movimiento(self):
        self._factura('2026-10-05', 1000, self.dolar)
        self._factura('2026-10-16', 200, self.dolar)
        asistente = self.env['cuenta.corriente.extracto'].create({'partner_id': self.cliente.id})
        self.assertEqual(asistente.fecha_desde, fields.Date.to_date('2026-10-05'))
        self.assertEqual(asistente.fecha_hasta, fields.Date.context_today(asistente))
        asistente.fecha_desde = '2026-10-10'  # se puede cambiar
        self.assertEqual(asistente.fecha_desde, fields.Date.to_date('2026-10-10'))

    def _cotizacion_de_hoy(self):
        hoy = fields.Date.context_today(self.env['res.currency.rate'].with_context(tz='America/Asuncion'))
        return self.env['res.currency.rate'].search([
            ('currency_id', '=', self.dolar.id), ('company_id', '=', self.env.company.id), ('name', '=', hoy)])

    def _dolarpy(self, referencial):
        respuesta = MagicMock()
        respuesta.json.return_value = {'dolarpy': {'bcp': {'compra': 1, 'venta': 2, 'referencial_diario': referencial}}}
        return patch.object(res_currency_rate.requests, 'get', return_value=respuesta)

    def test_la_cotizacion_del_bcp_se_carga_y_se_corrige_sola(self):
        Cotizacion = self.env['res.currency.rate']
        with self._dolarpy(5944.76):
            Cotizacion._cron_actualizar_cotizacion_dolar()
        self.assertRecordValues(self._cotizacion_de_hoy(), [{'inverse_company_rate': 5944.76, 'origen': 'bcp'}])
        # El BCP publicó la nueva: la tarea de cada 30 minutos corrige la de hoy.
        with self._dolarpy(5950):
            Cotizacion._cron_actualizar_cotizacion_dolar()
        self.assertRecordValues(self._cotizacion_de_hoy(), [{'inverse_company_rate': 5950, 'origen': 'bcp'}])

    def test_la_cargada_a_mano_no_la_pisa_la_tarea_pero_si_el_boton(self):
        Cotizacion = self.env['res.currency.rate']
        with self._dolarpy(5944.76):
            Cotizacion._cron_actualizar_cotizacion_dolar()
        self._cotizacion_de_hoy().write({'rate': 1 / 6100})
        self.assertEqual(self._cotizacion_de_hoy().origen, 'manual')
        with self._dolarpy(5950):
            Cotizacion._cron_actualizar_cotizacion_dolar()
        self.assertRecordValues(self._cotizacion_de_hoy(), [{'inverse_company_rate': 6100, 'origen': 'manual'}])
        with self._dolarpy(5950):
            accion = Cotizacion.action_traer_cotizacion_bcp()
        self.assertRecordValues(self._cotizacion_de_hoy(), [{'inverse_company_rate': 5950, 'origen': 'bcp'}])
        self.assertEqual(accion['params']['type'], 'success')

    def test_sin_internet_queda_la_cotizacion_anterior(self):
        with patch.object(res_currency_rate.requests, 'get', side_effect=res_currency_rate.requests.ConnectionError):
            self.env['res.currency.rate']._cron_actualizar_cotizacion_dolar()  # no falla: avisa en el log
            self.assertFalse(self._cotizacion_de_hoy())
            with self.assertRaises(UserError):
                self.env['res.currency.rate'].action_traer_cotizacion_bcp()

    def test_extracto_con_fechas_al_reves(self):
        asistente = self.env['cuenta.corriente.extracto'].create({
            'partner_id': self.cliente.id, 'fecha_desde': '2026-10-31', 'fecha_hasta': '2026-10-01',
        })
        with self.assertRaises(UserError):
            asistente.action_descargar_pdf()
