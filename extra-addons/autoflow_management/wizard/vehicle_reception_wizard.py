# -*- coding: utf-8 -*-
from odoo import Command, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.autoflow_management.models.workshop_order import SERVICE_TYPES


class AutoflowVehicleReceptionWizard(models.TransientModel):
    """Recepción rápida: el recepcionista anota combustible y daños y el vehículo pasa al taller."""
    _name = 'autoflow.vehicle.reception.wizard'
    _description = 'Recepción de vehículo'

    vehicle_id = fields.Many2one('autoflow.vehicle', string='Vehículo', required=True,
                                 domain="[('state', '!=', 'maintenance')]")
    partner_id = fields.Many2one('res.partner', string='Cliente', required=True)
    service_type = fields.Selection(SERVICE_TYPES, string='Tipo de servicio', required=True,
                                    default='preventive')
    mechanic_id = fields.Many2one('hr.employee', string='Mecánico')
    odometer = fields.Integer('Kilometraje')
    fuel_level = fields.Integer('Combustible (%)', default=50)
    damage_ids = fields.Many2many('autoflow.damage.type', relation='autoflow_reception_wizard_damage_rel',
                                  string='Daños visibles')
    customer_complaint = fields.Text('Motivo de ingreso')
    date_promised = fields.Datetime('Entrega prometida')

    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        if self.vehicle_id:
            self.odometer = self.vehicle_id.odometer
            if self.vehicle_id.partner_id:
                self.partner_id = self.vehicle_id.partner_id

    def action_confirm(self):
        self.ensure_one()
        if not 0 <= self.fuel_level <= 100:
            raise UserError('El nivel de combustible debe estar entre 0 y 100 %.')
        if self.odometer < self.vehicle_id.odometer:
            raise UserError(f'El kilometraje ingresado ({self.odometer}) es menor que el último registrado '
                            f'para el vehículo ({self.vehicle_id.odometer}). Revíselo.')
        order = self.env['autoflow.workshop.order'].create({
            'vehicle_id': self.vehicle_id.id,
            'partner_id': self.partner_id.id,
            'service_type': self.service_type,
            'mechanic_id': self.mechanic_id.id,
            'odometer': self.odometer,
            'fuel_level': self.fuel_level,
            'damage_ids': [Command.set(self.damage_ids.ids)],
            'customer_complaint': self.customer_complaint,
            'date_promised': self.date_promised,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Orden de servicio',
            'res_model': 'autoflow.workshop.order',
            'res_id': order.id,
            'view_mode': 'form',
            'target': 'current',
        }
