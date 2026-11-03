# -*- coding: utf-8 -*-
import logging

import requests

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import formatLang

_logger = logging.getLogger(__name__)

# DolarPy (gratis, sin clave): junta las cotizaciones del BCP, la SET y las casas de cambio de Paraguay.
URL_DOLARPY = 'https://dolar.melizeche.com/api/1.0/'
CAMPOS_COTIZACION = {'rate', 'company_rate', 'inverse_company_rate'}


class ResCurrencyRate(models.Model):
    _inherit = 'res.currency.rate'

    origen = fields.Selection(
        [('bcp', 'BCP'), ('manual', 'A mano')], 'Origen', default='manual', readonly=True,
        help='BCP: la trajo Odoo y la sigue corrigiendo sola durante el día. '
             'A mano: la cargó o la cambió alguien, y Odoo no la toca.')

    def write(self, vals):
        # Cambiar la cotización a mano la deja "A mano", para que la tarea de cada 30 minutos no la pise.
        if CAMPOS_COTIZACION & set(vals) and 'origen' not in vals:
            vals = dict(vals, origen='manual')
        return super().write(vals)

    @api.model
    def _cotizacion_bcp(self):
        """La cotización referencial diaria del dólar del BCP (la última publicada), en guaraníes."""
        respuesta = requests.get(URL_DOLARPY, timeout=20, headers={'User-Agent': 'Odoo cuenta_corriente'})
        respuesta.raise_for_status()
        cotizacion = float(respuesta.json()['dolarpy']['bcp']['referencial_diario'])
        if cotizacion <= 0:
            raise ValueError(f'cotización inválida: {cotizacion}')
        return cotizacion

    @api.model
    def _actualizar_cotizacion_dolar(self, reemplazar=False):
        """Deja la cotización del BCP como la de hoy en cada empresa en guaraníes: la crea si no hay y la corrige si
        el BCP publicó otra. Una cargada a mano solo se reemplaza con `reemplazar` (el botón). Devuelve la
        cotización y si cambió algo."""
        cotizacion = self._cotizacion_bcp()
        dolar = self.env.ref('base.USD')
        cambio = False
        empresas = self.env['res.company'].search([
            ('currency_id', '=', self.env.ref('base.PYG').id), ('parent_id', '=', False)])
        for empresa in empresas:
            hoy = fields.Date.context_today(self.with_context(tz=empresa.partner_id.tz or 'America/Asuncion'))
            de_hoy = self.search([('currency_id', '=', dolar.id), ('company_id', '=', empresa.id), ('name', '=', hoy)])
            if not de_hoy:
                self.create({'name': hoy, 'currency_id': dolar.id, 'company_id': empresa.id,
                             'rate': 1 / cotizacion, 'origen': 'bcp'})
                cambio = True
            elif de_hoy.origen == 'manual' and not reemplazar:
                continue
            elif de_hoy.origen == 'manual' or abs(1 / de_hoy.rate - cotizacion) >= 0.005:
                de_hoy.write({'rate': 1 / cotizacion, 'origen': 'bcp'})
                cambio = True
        return cotizacion, cambio

    @api.model
    def _cron_actualizar_cotizacion_dolar(self):
        # Si DolarPy no responde, queda la cotización anterior (Odoo usa la última cargada) y se avisa en el log.
        try:
            cotizacion, cambio = self._actualizar_cotizacion_dolar()
        except Exception as error:  # sin internet, la página caída o con otro formato
            _logger.warning('No se pudo traer la cotización del dólar del BCP: %s', error)
        else:
            if cambio:
                _logger.info('Cotización del dólar del BCP: %s Gs', cotizacion)

    def action_traer_cotizacion_bcp(self):
        """Botón de la lista de cotizaciones: trae la del BCP ahora y la deja como la de hoy, aunque se haya
        cargado otra a mano."""
        try:
            cotizacion, _cambio = self._actualizar_cotizacion_dolar(reemplazar=True)
        except Exception as error:
            raise UserError('No se pudo traer la cotización del BCP. Revisá la conexión a internet o cargala a mano.'
                            f'\n\nDetalle: {error}') from error
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Cotización del BCP',
                'message': f'Hoy: 1 USD = {formatLang(self.env, cotizacion, digits=2)} Gs',
                'type': 'success',
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }
