# -*- coding: utf-8 -*-
from odoo import fields, models

INSPECTION_STATES = [
    ('pending', 'Sin revisar'),
    ('ok', 'OK'),
    ('change', 'Requiere cambio'),
    ('damaged', 'Dañado'),
]


class AutoflowInspectionItem(models.Model):
    """Catálogo de puntos a revisar en la inspección de entrega (frenos, luces, fluidos...)."""
    _name = 'autoflow.inspection.item'
    _description = 'Punto de inspección'
    _order = 'sequence, id'

    name = fields.Char('Punto a revisar', required=True)
    sequence = fields.Integer(default=10)
    category = fields.Selection([
        ('safety', 'Seguridad'),
        ('mechanical', 'Mecánica'),
        ('electrical', 'Eléctrica'),
        ('body', 'Carrocería'),
    ], string='Categoría', required=True, default='mechanical')
    active = fields.Boolean(default=True)


class AutoflowInspectionLine(models.Model):
    """Detalle del checklist de entrega de una orden de servicio (maestro: la orden)."""
    _name = 'autoflow.inspection.line'
    _description = 'Ítem del checklist de entrega'
    _order = 'order_id, sequence, id'

    order_id = fields.Many2one('autoflow.workshop.order', string='Orden de servicio', required=True,
                               ondelete='cascade', index=True)
    item_id = fields.Many2one('autoflow.inspection.item', string='Punto a revisar', required=True,
                              ondelete='restrict')
    sequence = fields.Integer(related='item_id.sequence', store=True)
    category = fields.Selection(related='item_id.category', store=True)
    state = fields.Selection(INSPECTION_STATES, string='Estado', default='pending', required=True)
    notes = fields.Char('Observaciones')

    _sql_constraints = [
        ('item_uniq', 'unique(order_id, item_id)', 'Cada punto se revisa una sola vez por orden.'),
    ]


class AutoflowDamageType(models.Model):
    """Daños visibles que se marcan al recibir el vehículo (rayones, abolladuras...)."""
    _name = 'autoflow.damage.type'
    _description = 'Tipo de daño visible'
    _order = 'sequence, id'

    name = fields.Char('Daño', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
