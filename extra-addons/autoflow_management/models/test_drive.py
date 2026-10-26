# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import format_datetime

TEST_DRIVE_STATES = [
    ('scheduled', 'Agendada'),
    ('in_progress', 'En curso'),
    ('done', 'Finalizada'),
    ('cancel', 'Cancelada'),
]

# Un vehículo en el taller o ya vendido no se puede prestar para una prueba de manejo.
BLOCKED_VEHICLE_STATES = ('maintenance', 'sold')

DEFAULT_DURATION = timedelta(minutes=30)


class AutoflowTestDrive(models.Model):
    _name = 'autoflow.test.drive'
    _description = 'Prueba de manejo'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc, id desc'
    _check_company_auto = True

    name = fields.Char('Referencia', readonly=True, copy=False, default='Nuevo')
    partner_id = fields.Many2one('res.partner', string='Cliente', required=True, tracking=True,
                                 check_company=True)
    lead_id = fields.Many2one('crm.lead', string='Oportunidad', tracking=True, check_company=True,
                              index='btree_not_null')
    vehicle_id = fields.Many2one('autoflow.vehicle', string='Vehículo', required=True, tracking=True,
                                 check_company=True,
                                 domain="[('state', 'not in', ('maintenance', 'sold'))]")
    vehicle_state = fields.Selection(related='vehicle_id.state', string='Estado del vehículo')
    employee_id = fields.Many2one('hr.employee', string='Responsable', tracking=True, check_company=True,
                                  default=lambda self: self.env.user.employee_id)
    date_start = fields.Datetime('Inicio', required=True, tracking=True, default=fields.Datetime.now)
    date_end = fields.Datetime('Fin', required=True, tracking=True,
                               default=lambda self: fields.Datetime.now() + DEFAULT_DURATION)
    state = fields.Selection(TEST_DRIVE_STATES, string='Estado', default='scheduled', required=True,
                             tracking=True, copy=False)
    driver_license = fields.Char('Licencia de conducir')

    # Control de combustible (en %) y kilometraje al salir y al volver.
    fuel_start = fields.Integer('Combustible al salir (%)')
    fuel_end = fields.Integer('Combustible al volver (%)')
    odometer_start = fields.Integer('Km al salir')
    odometer_end = fields.Integer('Km al volver')
    distance = fields.Integer('Recorrido (km)', compute='_compute_distance', store=True)

    notes = fields.Text('Comentarios del cliente')
    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                 default=lambda self: self.env.company)
    sale_order_ids = fields.One2many('sale.order', 'test_drive_id', string='Cotizaciones')
    sale_order_count = fields.Integer(compute='_compute_sale_order_count')

    _sql_constraints = [
        ('fuel_start_range', 'CHECK(fuel_start BETWEEN 0 AND 100)',
         'El combustible al salir debe estar entre 0 y 100 %.'),
        ('fuel_end_range', 'CHECK(fuel_end BETWEEN 0 AND 100)',
         'El combustible al volver debe estar entre 0 y 100 %.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code('autoflow.test.drive') or 'Nuevo'
        return super().create(vals_list)

    @api.depends('odometer_start', 'odometer_end')
    def _compute_distance(self):
        for drive in self:
            drive.distance = max(drive.odometer_end - drive.odometer_start, 0) if drive.odometer_end else 0

    @api.depends('name', 'partner_id.name')
    def _compute_display_name(self):
        # Número y cliente: así se entiende en el calendario y en la cotización sin abrir la prueba.
        for drive in self:
            drive.display_name = f'{drive.name} · {drive.partner_id.name}' if drive.partner_id else drive.name

    def _compute_sale_order_count(self):
        for drive in self:
            drive.sale_order_count = len(drive.sale_order_ids)

    # Onchanges: solo corren en el formulario, para ayudar a quien carga los datos.

    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        if self.vehicle_id and self.state == 'scheduled':
            self.odometer_start = self.vehicle_id.odometer

    @api.onchange('lead_id')
    def _onchange_lead_id(self):
        if self.lead_id.partner_id:
            self.partner_id = self.lead_id.partner_id

    @api.onchange('date_start')
    def _onchange_date_start(self):
        if self.date_start and (not self.date_end or self.date_end <= self.date_start):
            self.date_end = self.date_start + DEFAULT_DURATION

    # Restricciones: corren siempre que se guardan estos campos, desde la pantalla o desde código.

    @api.constrains('vehicle_id', 'state')
    def _check_vehicle_available(self):
        for drive in self:
            if drive.state in ('scheduled', 'in_progress') and drive.vehicle_id.state in BLOCKED_VEHICLE_STATES:
                state_label = dict(drive.vehicle_id._fields['state'].selection)[drive.vehicle_id.state]
                raise ValidationError(
                    f'No se puede agendar una prueba de manejo con {drive.vehicle_id.display_name}: '
                    f'el vehículo está "{state_label}".')

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for drive in self:
            if drive.date_end <= drive.date_start:
                raise ValidationError('El fin de la prueba de manejo debe ser posterior al inicio.')

    @api.constrains('vehicle_id', 'date_start', 'date_end', 'state')
    def _check_overlap(self):
        for drive in self.filtered(lambda d: d.state != 'cancel'):
            overlapping = self.search([
                ('id', '!=', drive.id),
                ('vehicle_id', '=', drive.vehicle_id.id),
                ('state', '!=', 'cancel'),
                ('date_start', '<', drive.date_end),
                ('date_end', '>', drive.date_start),
            ], limit=1)
            if overlapping:
                raise ValidationError(
                    f'{drive.vehicle_id.display_name} ya tiene la prueba de manejo {overlapping.name} '
                    f'de {format_datetime(self.env, overlapping.date_start, dt_format="short")} '
                    f'a {format_datetime(self.env, overlapping.date_end, dt_format="short")}. '
                    'Elija otro horario u otro vehículo.')

    @api.constrains('odometer_start', 'odometer_end')
    def _check_odometer(self):
        for drive in self:
            if drive.odometer_end and drive.odometer_end < drive.odometer_start:
                raise ValidationError('El kilometraje al volver no puede ser menor que al salir.')

    # Botones

    def action_start(self):
        for drive in self:
            if drive.state != 'scheduled':
                raise UserError(f'La prueba de manejo {drive.name} no está agendada.')
            if drive.vehicle_id.state in BLOCKED_VEHICLE_STATES:
                raise UserError(f'{drive.vehicle_id.display_name} no está disponible para salir.')
            drive.write({
                'state': 'in_progress',
                'odometer_start': drive.odometer_start or drive.vehicle_id.odometer,
            })
        return True

    def action_done(self):
        """Cierra la prueba de manejo y deja el kilometraje del vehículo al día."""
        for drive in self:
            if drive.state != 'in_progress':
                raise UserError(f'La prueba de manejo {drive.name} no está en curso.')
            if not drive.odometer_end:
                raise UserError('Cargue el kilometraje con el que volvió el vehículo.')
            drive.state = 'done'
            drive.vehicle_id._update_odometer(drive.odometer_end)
        return True

    def action_cancel(self):
        if any(drive.state == 'done' for drive in self):
            raise UserError('No se puede cancelar una prueba de manejo finalizada.')
        self.state = 'cancel'
        return True

    def action_reschedule(self):
        self.filtered(lambda d: d.state == 'cancel').state = 'scheduled'
        return True

    def action_create_quotation(self):
        """Crea la cotización del vehículo probado, ligada a la oportunidad del CRM."""
        self.ensure_one()
        vehicle = self.vehicle_id
        if vehicle.state == 'sold':
            raise UserError(f'{vehicle.display_name} ya está vendido.')
        order_lines = []
        if vehicle.product_id:
            order_lines.append(Command.create({
                'product_id': vehicle.product_id.id,
                'name': f'{vehicle.display_name}\nChasis (VIN): {vehicle.vin}',
                'price_unit': vehicle.sale_price or vehicle.product_id.lst_price,
            }))
        order = self.env['sale.order'].create({
            'partner_id': self.partner_id.id,
            'opportunity_id': self.lead_id.id,
            'vehicle_id': vehicle.id,
            'test_drive_id': self.id,
            'origin': self.name,
            'company_id': self.company_id.id,
            'order_line': order_lines,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': order.id,
            'view_mode': 'form',
        }

    def action_view_sale_orders(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('sale.action_quotations_with_onboarding')
        action['domain'] = [('test_drive_id', '=', self.id)]
        action['context'] = {'create': False}
        return action
