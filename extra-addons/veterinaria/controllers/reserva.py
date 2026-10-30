# -*- coding: utf-8 -*-
import json
import os

from odoo import fields, http
from odoo.exceptions import UserError, ValidationError
from odoo.http import request
from odoo.tools import file_path

ARCHIVOS_PAGINA = ('veterinaria/static/reserva/reserva.css', 'veterinaria/static/reserva/reserva.js')


class ReservaPorInternet(http.Controller):
    """Página pública donde el dueño pide un turno para su mascota, como si chateara con la veterinaria.

    Odoo tiene que saber de qué base son los turnos: en un servidor con una sola base (o con --db-filter)
    funciona directo en /reservar.
    """

    def _reserva(self):
        reserva = request.env['vet.reserva'].sudo()
        return reserva.with_context(lang=reserva._idioma())

    def _servicios(self, servicio_ids):
        ids = [int(servicio_id) for servicio_id in servicio_ids or [] if str(servicio_id).isdigit()]
        return request.env['product.product'].sudo().browse(ids).exists()

    def _profesional(self, profesional_id):
        if not profesional_id or not str(profesional_id).isdigit():
            return None
        return request.env['hr.employee'].sudo().browse(int(profesional_id)).exists() or None

    @http.route('/reservar', type='http', auth='public', methods=['GET'], sitemap=False)
    def pagina(self, **_kwargs):
        datos = self._reserva()._datos_pagina()
        # Los archivos estáticos quedan una semana en el navegador: la fecha de cambio los renueva.
        version = int(max(os.path.getmtime(file_path(archivo)) for archivo in ARCHIVOS_PAGINA))
        return request.render('veterinaria.pagina_reserva', {
            'clinica': datos['clinica'],
            'datos': json.dumps(datos, ensure_ascii=False),
            'version': version,
        })

    @http.route('/reservar/horarios', type='json', auth='public', methods=['POST'])
    def horarios(self, servicio_ids, profesional_id=None, **_kwargs):
        try:
            return self._reserva()._dias(self._servicios(servicio_ids), self._profesional(profesional_id))
        except UserError as error:
            return {'error': error.args[0]}

    @http.route('/reservar/confirmar', type='json', auth='public', methods=['POST'])
    def confirmar(self, servicio_ids, inicio, datos, profesional_id=None, web=None, **_kwargs):
        if web:
            # Campo oculto: solo los robots lo completan.
            return {'error': 'No se pudo reservar el turno.'}
        if not isinstance(datos, dict):
            return {'error': 'Faltan tus datos.'}
        reserva = self._reserva()
        try:
            momento = fields.Datetime.to_datetime(inicio)
        except ValueError:
            return {'error': 'Elegí el día y la hora de nuevo, por favor.'}
        try:
            with request.env.cr.savepoint():
                atencion = reserva._reservar(self._servicios(servicio_ids), momento, datos,
                                             profesional=self._profesional(profesional_id))
        except (UserError, ValidationError) as error:
            return {'error': error.args[0]}
        return reserva._confirmacion(atencion, datos.get('nombre') or '')
