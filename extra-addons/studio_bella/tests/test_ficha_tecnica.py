# -*- coding: utf-8 -*-
from datetime import date, timedelta

from odoo.tests import Form, tagged

from odoo.addons.studio_bella.tests.common import StudioBellaCommon


@tagged('post_install', '-at_install')
class TestFichaTecnica(StudioBellaCommon):

    def test_ficha_cargada_desde_la_cita(self):
        cita = self._cita(servicios=self.color)
        with Form(cita) as formulario:
            with formulario.ficha_ids.new() as ficha:
                ficha.tipo = 'color'
                ficha.formula = '6.0 + 6.1 en partes iguales, oxidante 20 vol'
                ficha.tiempo_pose = 35

        ficha = cita.ficha_ids
        self.assertEqual(ficha.cliente_id, self.cliente)
        self.assertEqual(ficha.estilista_id, self.estilista)
        # La cita es el lunes 2/11 a las 10:00 de Asunción.
        self.assertEqual(ficha.fecha, date(2026, 11, 2))
        self.assertEqual(ficha.name, 'Color · 02/11/2026')
        self.assertEqual(self.cliente.bella_ficha_ids, ficha)

    def test_la_proxima_cita_muestra_los_trabajos_anteriores(self):
        primera = self._cita(servicios=self.color)
        anterior = self.env['bella.ficha.tecnica'].create({
            'cita_id': primera.id, 'formula': '7.1 con oxidante 20 vol', 'tiempo_pose': 30,
        })
        otra_clienta = self.env['res.partner'].create({'name': 'Otra clienta'})
        self.env['bella.ficha.tecnica'].create({'cliente_id': otra_clienta.id, 'formula': 'Mechas con papel'})

        segunda = self._cita(inicio=self.lunes_10 + timedelta(weeks=5), servicios=self.color)
        nueva = self.env['bella.ficha.tecnica'].create({'cita_id': segunda.id, 'formula': '7.1 + 7.0'})
        self.assertEqual(segunda.ficha_anterior_ids, anterior)
        self.assertEqual(segunda.ficha_ids, nueva)
        self.assertEqual(primera.ficha_anterior_ids, nueva)

    def test_la_ficha_sigue_a_la_cita(self):
        cita = self._cita(servicios=self.color)
        ficha = self.env['bella.ficha.tecnica'].create({'cita_id': cita.id, 'formula': '7.1 con oxidante 20 vol'})
        # Se había cargado la cita a otra clienta y otro día: al corregirla, la ficha la sigue.
        otra = self.env['res.partner'].create({'name': 'Clienta correcta'})
        cita.write({'cliente_id': otra.id, 'fecha_inicio': self.lunes_10 + timedelta(days=1)})
        self.assertEqual(ficha.cliente_id, otra)
        self.assertEqual(ficha.fecha, date(2026, 11, 3))
        self.assertEqual(otra.bella_ficha_ids, ficha)
        self.assertFalse(self.cliente.bella_ficha_ids)

    def test_alergias_a_la_vista_en_la_cita(self):
        cita = self._cita()
        self.assertFalse(cita.cliente_alergias)
        self.cliente.bella_alergias = 'Alergia a la parafenilendiamina (PPD)'
        self.assertEqual(cita.cliente_alergias, 'Alergia a la parafenilendiamina (PPD)')

        # El tipo de cabello se puede corregir desde la cita y queda en la clienta.
        cita.cliente_tipo_cabello = 'Fino, 30 % de canas'
        self.assertEqual(self.cliente.bella_tipo_cabello, 'Fino, 30 % de canas')
