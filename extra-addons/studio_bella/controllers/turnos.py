# -*- coding: utf-8 -*-
import json
import os

from odoo import fields, http
from odoo.exceptions import UserError, ValidationError
from odoo.http import request
from odoo.tools import file_path

ARCHIVOS_PAGINA = ('studio_bella/static/turnos/turnos.css', 'studio_bella/static/turnos/turnos.js')


class TurnosPorInternet(http.Controller):
    """Página pública donde las clientas reservan su turno, sin usuario ni contraseña.

    Odoo tiene que saber de qué base son los turnos: en un servidor con una sola base (o con --db-filter)
    funciona directo en /turnos.
    """

    def _turnos(self):
        turnos = request.env['bella.turnos'].sudo()
        return turnos.with_context(lang=turnos._idioma())

    def _servicios(self, servicio_ids):
        ids = [int(servicio_id) for servicio_id in servicio_ids or [] if str(servicio_id).isdigit()]
        return request.env['product.product'].sudo().browse(ids).exists()

    def _estilista(self, estilista_id):
        if not estilista_id or not str(estilista_id).isdigit():
            return None
        return request.env['hr.employee'].sudo().browse(int(estilista_id)).exists() or None

    @http.route('/turnos', type='http', auth='public', methods=['GET'], sitemap=False)
    def pagina(self, **_kwargs):
        datos = self._turnos()._datos_pagina()
        # Los archivos estáticos quedan una semana en el navegador: la fecha de cambio los renueva.
        version = int(max(os.path.getmtime(file_path(archivo)) for archivo in ARCHIVOS_PAGINA))
        return request.render('studio_bella.pagina_turnos', {
            'salon': datos['salon'],
            'datos': json.dumps(datos, ensure_ascii=False),
            'version': version,
        })

    @http.route('/turnos/horarios', type='json', auth='public', methods=['POST'])
    def horarios(self, servicio_ids, estilista_id=None, **_kwargs):
        return self._turnos()._dias(self._servicios(servicio_ids), self._estilista(estilista_id))

    @http.route('/turnos/reservar', type='json', auth='public', methods=['POST'])
    def reservar(self, servicio_ids, inicio, nombre, telefono, estilista_id=None, email=None, nota=None, web=None,
                 **_kwargs):
        if web:
            # Campo oculto: solo los robots lo completan.
            return {'error': 'No se pudo reservar el turno.'}
        turnos = self._turnos()
        try:
            momento = fields.Datetime.to_datetime(inicio)
        except ValueError:
            return {'error': 'Elegí el día y la hora de nuevo, por favor.'}
        try:
            with request.env.cr.savepoint():
                citas = turnos._reservar(self._servicios(servicio_ids), momento, nombre, telefono,
                                         estilista=self._estilista(estilista_id), email=email, nota=nota)
        except (UserError, ValidationError) as error:
            return {'error': error.args[0]}
        return turnos._confirmacion(citas, nombre)
