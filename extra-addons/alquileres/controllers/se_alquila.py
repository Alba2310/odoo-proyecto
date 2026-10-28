# -*- coding: utf-8 -*-
import os
from urllib.parse import quote

from odoo import http
from odoo.http import request
from odoo.tools import file_path

from ..models.utiles import guaranies, numero_whatsapp

ARCHIVOS_PAGINA = ('alquileres/static/se_alquila/se_alquila.css', 'alquileres/static/se_alquila/se_alquila.js')


class PaginaSeAlquila(http.Controller):
    """Página pública con las unidades libres, para que los interesados consulten por WhatsApp o dejen sus datos.

    Odoo tiene que saber de qué base son las unidades: la atiende el servicio `oga` de docker-compose, que tiene
    una sola base (--db-filter), en http://se-alquila.localhost:8072/se-alquila.
    """

    def _unidades(self):
        return request.env['alquiler.unidad'].sudo().search(
            [('estado', '=', 'libre'), ('publicar', '=', True)], order='propiedad_id, piso, name')

    def _whatsapp(self, empresa, texto):
        numero = numero_whatsapp(empresa.phone, str(empresa.country_id.phone_code or 595))
        return f'https://wa.me/{numero}?text={quote(texto)}' if numero else ''

    @http.route('/se-alquila', type='http', auth='public', methods=['GET'], sitemap=False)
    def pagina(self, gracias=None, **_kwargs):
        empresa = request.env.company.sudo()
        unidades = [{
            'id': unidad.id,
            'nombre': unidad.display_name,
            'ciudad': unidad.ciudad,
            'precio': guaranies(unidad.alquiler_sugerido) if unidad.alquiler_sugerido else '',
            'dormitorios': unidad.dormitorios,
            'banos': unidad.banos,
            'descripcion': unidad.detalle_web or unidad.descripcion or '',
            'foto': bool(unidad.foto or unidad.propiedad_id.foto),
            'whatsapp': self._whatsapp(empresa, f'Hola, vi en la página que se alquila {unidad.display_name} '
                                                f'({unidad.ciudad}) y quiero más información.'),
        } for unidad in self._unidades()]
        # Los archivos estáticos quedan una semana en el navegador: la fecha de cambio los renueva.
        version = int(max(os.path.getmtime(file_path(archivo)) for archivo in ARCHIVOS_PAGINA))
        return request.render('alquileres.pagina_se_alquila', {
            'empresa': empresa,
            'unidades': unidades,
            'ciudades': sorted({unidad['ciudad'] for unidad in unidades}),
            'whatsapp': self._whatsapp(empresa, 'Hola, quiero consultar por los alquileres.'),
            'gracias': bool(gracias),
            'csrf_token': request.csrf_token(),
            'version': version,
        })

    @http.route('/se-alquila/foto/<int:unidad_id>', type='http', auth='public', methods=['GET'], sitemap=False)
    def foto(self, unidad_id, **_kwargs):
        unidad = self._unidades().filtered(lambda u: u.id == unidad_id)
        if not unidad:
            raise request.not_found()
        registro = unidad if unidad.foto else unidad.propiedad_id
        return request.env['ir.binary']._get_image_stream_from(
            registro, 'foto', width=800, height=600, crop=True).get_response()

    @http.route('/se-alquila/consulta', type='http', auth='public', methods=['POST'], sitemap=False)
    def consulta(self, nombre='', telefono='', email='', unidad_id='', mensaje='', web='', **_kwargs):
        if web:
            # Campo oculto: solo los robots lo completan.
            return request.redirect('/se-alquila?gracias=1#consulta')
        nombre, telefono = nombre.strip(), telefono.strip()
        if not nombre or not telefono:
            return request.redirect('/se-alquila#consulta')
        unidad = self._unidades().filtered(lambda u: str(u.id) == unidad_id)
        request.env['alquiler.interesado'].sudo().create({
            'name': nombre[:100],
            'telefono': telefono[:40],
            'email': email.strip()[:100] or False,
            'unidad_id': unidad.id,
            'mensaje': mensaje.strip()[:2000] or False,
            'desde_la_pagina': True,
        })
        return request.redirect('/se-alquila?gracias=1#consulta')
