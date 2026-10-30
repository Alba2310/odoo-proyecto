# -*- coding: utf-8 -*-
from odoo import fields, models

from .utiles import EMOJIS

ICONOS = [
    ('perro', 'Perro'),
    ('gato', 'Gato'),
    ('ave', 'Ave'),
    ('conejo', 'Conejo'),
    ('roedor', 'Roedor'),
    ('reptil', 'Reptil'),
    ('pez', 'Pez'),
    ('otro', 'Otro'),
]


class VetEspecie(models.Model):
    _name = 'vet.especie'
    _description = 'Especie'
    _order = 'sequence, name'

    name = fields.Char('Especie', required=True, translate=True)
    sequence = fields.Integer(default=10)
    icono = fields.Selection(ICONOS, string='Dibujo', required=True, default='otro',
                             help='Lo que se muestra en el tablero y en la página de turnos cuando la mascota no '
                                  'tiene foto.')
    emoji = fields.Char(compute='_compute_emoji')
    raza_ids = fields.One2many('vet.raza', 'especie_id', string='Razas')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('nombre_unico', 'UNIQUE(name)', 'Ya existe esa especie.'),
    ]

    def _compute_emoji(self):
        for especie in self:
            especie.emoji = EMOJIS.get(especie.icono, EMOJIS['otro'])


class VetRaza(models.Model):
    _name = 'vet.raza'
    _description = 'Raza'
    _order = 'especie_id, name'

    name = fields.Char('Raza', required=True)
    especie_id = fields.Many2one('vet.especie', string='Especie', required=True, ondelete='cascade', index=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('nombre_unico', 'UNIQUE(especie_id, name)', 'Esa raza ya está cargada para la especie.'),
    ]
