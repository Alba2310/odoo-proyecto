# -*- coding: utf-8 -*-
from datetime import date, timedelta
from urllib.parse import unquote

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.veterinaria.tests.common import PatitasCommon


@tagged('post_install', '-at_install')
class TestAplicacion(PatitasCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.michi = cls.env['vet.mascota'].create({
            'name': 'Michi', 'dueno_id': cls.duena.id, 'especie_id': cls.gato.id, 'sexo': 'hembra',
        })
        cls.hoy = fields.Date.context_today(cls.env.user)

    def _aplicar(self, mascota, fecha, producto=None, **valores):
        return self.env['vet.aplicacion'].create({
            'mascota_id': mascota.id, 'producto_id': (producto or self.antirrabica).id, 'fecha': fecha, **valores,
        })

    def test_la_dosis_nueva_renueva_la_anterior(self):
        vieja = self._aplicar(self.toby, date(2025, 3, 1))
        self.assertEqual(vieja.proxima_fecha, date(2026, 3, 1))
        self.assertFalse(vieja.renovada)
        self.assertEqual(vieja.estado_dosis, 'vencida' if self.hoy > date(2026, 3, 1) else 'al_dia')
        nueva = self._aplicar(self.toby, date(2026, 3, 5))
        self.assertTrue(vieja.renovada)
        self.assertFalse(nueva.renovada)
        self.assertEqual(vieja.estado_dosis, 'renovada')
        # La de otra mascota no cuenta.
        self.assertFalse(self._aplicar(self.michi, date(2025, 1, 1)).renovada)
        # Si se borra la nueva, la vieja vuelve a estar pendiente.
        nueva.unlink()
        self.assertFalse(vieja.renovada)

    def test_la_proxima_dosis_va_despues(self):
        with self.assertRaises(ValidationError):
            self._aplicar(self.toby, self.hoy, proxima_fecha=self.hoy - timedelta(days=1))

    def test_un_solo_whatsapp_con_las_dosis_de_todas_sus_mascotas(self):
        toby = self._aplicar(self.toby, self.hoy - timedelta(days=360))  # le toca en 5 días
        michi = self._aplicar(self.michi, self.hoy - timedelta(days=400))  # se le venció hace 35 días
        lejana = self._aplicar(self.toby, self.hoy, producto=self.env['product.product'].create({
            'name': 'Séxtuple de prueba', 'type': 'consu', 'vet_aplicacion': 'vacuna', 'vet_dias_refuerzo': 365,
        }))
        accion = toby.action_avisar_whatsapp()
        texto = unquote(accion['url'])
        self.assertTrue(accion['url'].startswith('https://wa.me/595981000900?text='))
        self.assertIn('¡Hola Ana!', texto)
        self.assertIn('• Toby: Antirrábica de prueba, el ', texto)
        self.assertIn('• Michi: Antirrábica de prueba, que le tocaba el', texto)
        self.assertNotIn('Séxtuple', texto)
        self.assertIn('/reservar', texto)
        self.assertEqual(toby.avisada_el, self.hoy)
        self.assertEqual(michi.avisada_el, self.hoy)
        self.assertFalse(lejana.avisada_el)
        # Si se corrige la fecha, se vuelve a avisar.
        toby.proxima_fecha = self.hoy + timedelta(days=10)
        self.assertFalse(toby.avisada_el)

    def test_no_se_avisa_lo_que_no_se_repite(self):
        sin_refuerzo = self._aplicar(self.toby, self.hoy, producto=self.env['product.product'].create({
            'name': 'Vacuna única de prueba', 'type': 'consu', 'vet_aplicacion': 'vacuna',
        }))
        self.assertFalse(sin_refuerzo.proxima_fecha)
        self.assertEqual(sin_refuerzo.estado_dosis, 'sin_refuerzo')
        with self.assertRaises(UserError):
            sin_refuerzo.action_avisar_whatsapp()

    def test_correo_unos_dias_antes(self):
        self.company.vet_dias_aviso_vacuna = 7
        en_una_semana = self._aplicar(self.toby, self.hoy - timedelta(days=358))
        en_un_mes = self._aplicar(self.michi, self.hoy - timedelta(days=335))
        fallecida = self.env['vet.mascota'].create({
            'name': 'Firulais', 'dueno_id': self.duena.id, 'especie_id': self.perro.id, 'fallecida': True,
        })
        de_la_fallecida = self._aplicar(fallecida, self.hoy - timedelta(days=360))
        correos = self.env['mail.mail'].search_count([])
        self.env['vet.aplicacion']._cron_avisos()
        self.assertEqual(en_una_semana.avisada_el, self.hoy)
        self.assertFalse(en_un_mes.avisada_el)
        self.assertFalse(de_la_fallecida.avisada_el)
        self.assertEqual(self.env['mail.mail'].search_count([]), correos + 1)
        self.assertIn('Aviso de la próxima dosis por correo', self.toby.message_ids[0].body)
