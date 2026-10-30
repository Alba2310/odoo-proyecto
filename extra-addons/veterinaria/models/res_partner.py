# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    vet_mascota_ids = fields.One2many('vet.mascota', 'dueno_id', string='Mascotas',
                                      groups='veterinaria.group_vet_personal')
    vet_mascota_count = fields.Integer('Cantidad de mascotas', compute='_compute_vet_mascota_count',
                                       groups='veterinaria.group_vet_personal')

    def _compute_vet_mascota_count(self):
        cantidades = dict(self.env['vet.mascota']._read_group(
            [('dueno_id', 'in', self.ids)], ['dueno_id'], ['__count']))
        for partner in self:
            partner.vet_mascota_count = cantidades.get(partner, 0)

    def action_vet_ver_mascotas(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('veterinaria.action_vet_mascota')
        action['domain'] = [('dueno_id', '=', self.id)]
        action['context'] = {'default_dueno_id': self.id}
        return action
