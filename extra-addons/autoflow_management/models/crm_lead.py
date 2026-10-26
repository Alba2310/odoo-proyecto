# -*- coding: utf-8 -*-
from odoo import fields, models


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    test_drive_ids = fields.One2many('autoflow.test.drive', 'lead_id', string='Pruebas de manejo')
    test_drive_count = fields.Integer(compute='_compute_test_drive_count')

    def _compute_test_drive_count(self):
        for lead in self:
            lead.test_drive_count = len(lead.test_drive_ids)

    def action_view_test_drives(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('autoflow_management.action_autoflow_test_drive')
        action['domain'] = [('lead_id', '=', self.id)]
        action['context'] = {
            'default_lead_id': self.id,
            'default_partner_id': self.partner_id.id,
        }
        return action
