# -*- coding: utf-8 -*-
from odoo import api, fields, models


class TiendaCajaCierreWizard(models.TransientModel):
    _name = 'tienda.caja.cierre.wizard'
    _description = 'Asistente para cerrar la caja'

    caja_id = fields.Many2one('tienda.caja', string='Caja', required=True, readonly=True)
    currency_id = fields.Many2one(related='caja_id.currency_id')
    efectivo_esperado = fields.Monetary(related='caja_id.efectivo_esperado')
    efectivo_contado = fields.Monetary('Efectivo contado', required=True,
                                       help='Todo el efectivo que hay en la caja ahora, incluido el fondo inicial.')
    diferencia = fields.Monetary('Diferencia', compute='_compute_diferencia')
    nota = fields.Text('Notas', help='Por ejemplo, el motivo de una diferencia.')

    @api.depends('efectivo_contado', 'efectivo_esperado')
    def _compute_diferencia(self):
        for asistente in self:
            asistente.diferencia = asistente.efectivo_contado - asistente.efectivo_esperado

    def action_cerrar(self):
        """Cierra la caja y descarga el resumen de cierre para imprimir."""
        self.ensure_one()
        self.caja_id._cerrar(self.efectivo_contado, self.nota)
        # config=False: el ticket no usa el diseño de documentos de la compañía, así que
        # no hace falta que Odoo pida configurarlo antes de imprimir.
        return self.env.ref('tienda_ventas.action_report_cierre_caja').report_action(self.caja_id, config=False)
