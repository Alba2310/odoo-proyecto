# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    bella_cita_count = fields.Integer('Citas', compute='_compute_bella_cita_count',
                                      groups='studio_bella.group_bella_recepcion')

    def _compute_bella_cita_count(self):
        cantidades = dict(self.env['bella.cita']._read_group(
            [('cliente_id', 'in', self.ids)], ['cliente_id'], ['__count']))
        for partner in self:
            partner.bella_cita_count = cantidades.get(partner, 0)

    def action_bella_ver_citas(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('studio_bella.action_bella_cita')
        action['domain'] = [('cliente_id', '=', self.id)]
        action['context'] = {'default_cliente_id': self.id}
        action['view_mode'] = 'list,calendar,form'
        action['views'] = [(False, 'list'), (False, 'calendar'), (False, 'form')]
        return action
