# -*- coding: utf-8 -*-
from odoo import api, fields, models

CATEGORIAS_GASTO = [
    ('reparacion', 'Reparación y mantenimiento'),
    ('impuesto', 'Impuesto inmobiliario'),
    ('servicios', 'ANDE, agua e internet'),
    ('limpieza', 'Limpieza y áreas comunes'),
    ('comision', 'Comisión de administración'),
    ('seguro', 'Seguro'),
    ('otro', 'Otro'),
]


class AlquilerGasto(models.Model):
    """Lo que el dueño gasta en una propiedad. Con los pagos de los inquilinos da la ganancia real."""
    _name = 'alquiler.gasto'
    _description = 'Gasto de una propiedad'
    _order = 'fecha desc, id desc'

    name = fields.Char('Descripción', required=True)
    fecha = fields.Date('Fecha', required=True, default=fields.Date.context_today)
    propiedad_id = fields.Many2one('alquiler.propiedad', string='Propiedad', required=True, index=True)
    unidad_id = fields.Many2one('alquiler.unidad', string='Unidad', domain="[('propiedad_id', '=', propiedad_id)]",
                                help='Vacío si es de toda la propiedad (por ejemplo, la luz del pasillo).')
    categoria = fields.Selection(CATEGORIAS_GASTO, string='Categoría', required=True, default='reparacion')
    monto = fields.Monetary('Monto', required=True)
    proveedor = fields.Char('Pagado a', help='Quién cobró: el plomero, la ANDE, la municipalidad...')
    comprobante = fields.Binary('Comprobante', attachment=True)
    comprobante_nombre = fields.Char('Nombre del comprobante')
    mantenimiento_id = fields.Many2one('alquiler.mantenimiento', string='Reparación', readonly=True,
                                       ondelete='set null')
    company_id = fields.Many2one(related='propiedad_id.company_id', store=True)
    currency_id = fields.Many2one(related='company_id.currency_id')

    _sql_constraints = [
        ('monto_positivo', 'CHECK(monto > 0)', 'El monto del gasto tiene que ser mayor a cero.'),
    ]

    @api.onchange('unidad_id')
    def _onchange_unidad_id(self):
        if self.unidad_id:
            self.propiedad_id = self.unidad_id.propiedad_id
