# -*- coding: utf-8 -*-
from odoo import Command, api, fields, models

from .utiles import fecha_larga

TIPOS_ACTA = [
    ('entrada', 'Entrada: se entrega al inquilino'),
    ('salida', 'Salida: el inquilino la devuelve'),
]
ESTADOS_ELEMENTO = [
    ('bueno', 'Bueno'),
    ('regular', 'Regular'),
    ('malo', 'Malo'),
    ('no_tiene', 'No tiene'),
]
# Lo que se revisa en cada entrega; se puede agregar o sacar en cada acta.
ELEMENTOS = [
    'Paredes y pintura',
    'Pisos',
    'Puertas y cerraduras',
    'Ventanas y vidrios',
    'Baño (inodoro, lavatorio, ducha)',
    'Cocina y mesada',
    'Instalación eléctrica y enchufes',
    'Canillas y cañerías',
    'Aire acondicionado y ventiladores',
    'Muebles',
]


class AlquilerActa(models.Model):
    """Acta de entrega: cómo está la unidad cuando entra o sale el inquilino, con fotos, lecturas de los medidores
    y llaves. La de salida sirve para decidir cuánto se descuenta del depósito."""
    _name = 'alquiler.acta'
    _description = 'Acta de entrega'
    _inherit = ['mail.thread']
    _order = 'fecha desc, id desc'

    name = fields.Char('Nombre', compute='_compute_name', store=True)
    contrato_id = fields.Many2one('alquiler.contrato', string='Contrato', required=True, ondelete='cascade',
                                  index=True)
    unidad_id = fields.Many2one(related='contrato_id.unidad_id', store=True, string='Unidad')
    propiedad_id = fields.Many2one(related='contrato_id.propiedad_id', store=True, string='Propiedad')
    inquilino_id = fields.Many2one(related='contrato_id.inquilino_id', store=True, string='Inquilino')
    company_id = fields.Many2one(related='contrato_id.company_id', store=True)
    tipo = fields.Selection(TIPOS_ACTA, string='Tipo', required=True, default='entrada')
    fecha = fields.Date('Fecha', required=True, default=fields.Date.context_today)
    linea_ids = fields.One2many('alquiler.acta.linea', 'acta_id', string='Estado de la unidad', copy=True)
    lectura_ande = fields.Char('Medidor de ANDE')
    lectura_agua = fields.Char('Medidor de agua')
    llaves = fields.Integer('Llaves entregadas')
    foto_ids = fields.Many2many('ir.attachment', string='Fotos')
    observaciones = fields.Text('Observaciones')

    @api.depends('tipo', 'unidad_id', 'fecha')
    def _compute_name(self):
        for acta in self:
            tipo = 'entrada' if acta.tipo == 'entrada' else 'salida'
            acta.name = f'Acta de {tipo} · {acta.unidad_id.display_name or ""}'

    @api.model
    def default_get(self, campos):
        valores = super().default_get(campos)
        if 'linea_ids' in campos and not valores.get('linea_ids'):
            valores['linea_ids'] = [Command.create({'elemento': elemento, 'sequence': orden})
                                    for orden, elemento in enumerate(ELEMENTOS)]
        return valores

    def _fecha_texto(self):
        return fecha_larga(self.fecha)

    def _fotos(self):
        return self.foto_ids.filtered(lambda adjunto: (adjunto.mimetype or '').startswith('image/'))


class AlquilerActaLinea(models.Model):
    _name = 'alquiler.acta.linea'
    _description = 'Elemento revisado en el acta de entrega'
    _order = 'acta_id, sequence, id'

    acta_id = fields.Many2one('alquiler.acta', string='Acta', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer('Orden', default=10)
    elemento = fields.Char('Qué se revisó', required=True)
    estado = fields.Selection(ESTADOS_ELEMENTO, string='Estado', required=True, default='bueno')
    nota = fields.Char('Nota')
