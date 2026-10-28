# -*- coding: utf-8 -*-
from odoo import fields, models

from .cuota import CALIFICACIONES, calificar


class ResPartner(models.Model):
    _inherit = 'res.partner'

    alquiler_es_inquilino = fields.Boolean('Inquilino', help='Aparece en la lista de inquilinos de Óga.')
    alquiler_contrato_count = fields.Integer('Alquileres', compute='_compute_alquiler_contrato_count',
                                             groups='alquileres.group_alquiler_encargado')
    alquiler_puntaje = fields.Selection(CALIFICACIONES, string='Cómo paga', compute='_compute_alquiler_puntaje',
                                        groups='alquileres.group_alquiler_encargado')
    alquiler_puntaje_texto = fields.Char('Pagos a tiempo', compute='_compute_alquiler_puntaje',
                                         groups='alquileres.group_alquiler_encargado')

    def _compute_alquiler_contrato_count(self):
        cantidades = dict(self.env['alquiler.contrato']._read_group(
            [('inquilino_id', 'in', self._origin.ids)], ['inquilino_id'], ['__count']))
        for partner in self:
            partner.alquiler_contrato_count = cantidades.get(partner._origin, 0)

    def _compute_alquiler_puntaje(self):
        """Cómo paga en todos sus alquileres (también los de contratos terminados)."""
        hoy = fields.Date.context_today(self)
        cuotas = self.env['alquiler.cuota'].search([('inquilino_id', 'in', self._origin.ids)])
        for partner in self:
            partner.alquiler_puntaje, partner.alquiler_puntaje_texto = calificar(
                cuotas.filtered(lambda c: c.inquilino_id == partner._origin), hoy)

    def action_alquiler_ver_contratos(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('alquileres.action_alquiler_contrato')
        action['domain'] = [('inquilino_id', '=', self.id)]
        action['context'] = {'default_inquilino_id': self.id}
        return action
