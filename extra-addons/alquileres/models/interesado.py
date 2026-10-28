# -*- coding: utf-8 -*-
from urllib.parse import quote

from odoo import api, fields, models
from odoo.exceptions import UserError

from .utiles import numero_whatsapp, primer_nombre

ESTADOS_INTERESADO = [
    ('nuevo', 'Nuevo'),
    ('contactado', 'Contactado'),
    ('visita', 'Visita agendada'),
    ('alquilo', 'Alquiló'),
    ('descartado', 'Descartado'),
]


class AlquilerInteresado(models.Model):
    """Alguien que consultó por una unidad libre, casi siempre desde la página "Se alquila"."""
    _name = 'alquiler.interesado'
    _description = 'Interesado en alquilar'
    _inherit = ['mail.thread']
    _order = 'create_date desc, id desc'

    name = fields.Char('Nombre', required=True)
    telefono = fields.Char('Teléfono', required=True)
    email = fields.Char('Correo')
    unidad_id = fields.Many2one('alquiler.unidad', string='Unidad que le interesa', index=True)
    mensaje = fields.Text('Mensaje')
    estado = fields.Selection(ESTADOS_INTERESADO, string='Estado', default='nuevo', required=True, tracking=True,
                              group_expand='_group_expand_estado')
    desde_la_pagina = fields.Boolean('Desde la página', readonly=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                 default=lambda self: self.env.company)

    @api.model
    def _group_expand_estado(self, estados, domain):
        return [clave for clave, _etiqueta in ESTADOS_INTERESADO]

    def action_whatsapp(self):
        self.ensure_one()
        numero = numero_whatsapp(self.telefono, str(self.company_id.country_id.phone_code or 595))
        if not numero:
            raise UserError(f'{self.name} no dejó un teléfono válido.')
        unidad = f' por {self.unidad_id.display_name}' if self.unidad_id else ''
        texto = (f'¡Hola {primer_nombre(self.name)}! Te escribimos de {self.company_id.name}{unidad}, que '
                 'consultaste en nuestra página. ¿Cuándo te queda bien para verla?')
        if self.estado == 'nuevo':
            self.estado = 'contactado'
        return {'type': 'ir.actions.act_url', 'url': f'https://wa.me/{numero}?text={quote(texto)}', 'target': 'new'}
