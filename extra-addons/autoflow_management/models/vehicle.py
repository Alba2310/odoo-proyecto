# -*- coding: utf-8 -*-
import re

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

VEHICLE_STATES = [
    ('available', 'Disponible'),
    ('maintenance', 'En mantenimiento'),
    ('reserved', 'Reservado'),
    ('sold', 'Vendido'),
]

# El VIN tiene 17 caracteres y no usa I, O ni Q para no confundirlas con 1 y 0.
VIN_PATTERN = re.compile(r'^[A-HJ-NPR-Z0-9]{17}$')


class AutoflowVehicleBrand(models.Model):
    _name = 'autoflow.vehicle.brand'
    _description = 'Marca de vehículo'
    _order = 'name'

    name = fields.Char('Marca', required=True)
    image_128 = fields.Image('Logo', max_width=128, max_height=128)
    model_ids = fields.One2many('autoflow.vehicle.model', 'brand_id', string='Modelos')

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Ya existe una marca con ese nombre.'),
    ]


class AutoflowVehicleModel(models.Model):
    _name = 'autoflow.vehicle.model'
    _description = 'Modelo de vehículo'
    _order = 'brand_id, name'

    name = fields.Char('Modelo', required=True)
    brand_id = fields.Many2one('autoflow.vehicle.brand', string='Marca', required=True, ondelete='restrict')
    vehicle_ids = fields.One2many('autoflow.vehicle', 'model_id', string='Vehículos')

    _sql_constraints = [
        ('name_brand_uniq', 'unique(brand_id, name)', 'Ese modelo ya existe para la marca.'),
    ]

    @api.depends('brand_id.name', 'name')
    def _compute_display_name(self):
        for model in self:
            model.display_name = f'{model.brand_id.name} {model.name}' if model.brand_id else model.name


class AutoflowVehicle(models.Model):
    _name = 'autoflow.vehicle'
    _description = 'Vehículo'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _order = 'name, year desc'
    _rec_names_search = ['name', 'vin', 'license_plate']
    _check_company_auto = True

    name = fields.Char('Vehículo', compute='_compute_name', store=True)
    active = fields.Boolean(default=True)
    model_id = fields.Many2one('autoflow.vehicle.model', string='Modelo', required=True, tracking=True)
    brand_id = fields.Many2one(related='model_id.brand_id', store=True, string='Marca')
    year = fields.Integer('Año', required=True, default=lambda self: fields.Date.today().year)
    vin = fields.Char('N.º de chasis (VIN)', required=True, copy=False, tracking=True)
    license_plate = fields.Char('Chapa', copy=False, tracking=True)
    color = fields.Char('Color')
    odometer = fields.Integer('Kilometraje actual', tracking=True)
    state = fields.Selection(VEHICLE_STATES, string='Estado', default='available', required=True,
                             tracking=True, group_expand=True)
    partner_id = fields.Many2one('res.partner', string='Propietario', tracking=True, check_company=True,
                                 help='Cliente dueño del vehículo: lo compró aquí o lo trae al taller.')
    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    # Solo para el Responsable; el historial del chatter tampoco se lo muestra a los demás.
    acquisition_cost = fields.Monetary('Costo de adquisición', tracking=True,
                                       groups='autoflow_management.group_autoflow_manager')
    sale_price = fields.Monetary('Precio de venta', tracking=True)
    product_id = fields.Many2one('product.product', string='Producto de venta', check_company=True,
                                 help='Producto que se usa en la cotización cuando se vende este vehículo.')
    photo_ids = fields.One2many('autoflow.vehicle.photo', 'vehicle_id', string='Galería de fotos')
    notes = fields.Html('Notas')

    test_drive_ids = fields.One2many('autoflow.test.drive', 'vehicle_id', string='Pruebas de manejo')
    workshop_order_ids = fields.One2many('autoflow.workshop.order', 'vehicle_id', string='Órdenes de servicio')
    sale_order_ids = fields.One2many('sale.order', 'vehicle_id', string='Cotizaciones')
    test_drive_count = fields.Integer(compute='_compute_counts')
    workshop_order_count = fields.Integer(compute='_compute_counts')
    sale_order_count = fields.Integer(compute='_compute_counts')
    workshop_amount_total = fields.Monetary('Gastado en taller', compute='_compute_workshop_amount_total',
                                            help='Suma de las órdenes de servicio finalizadas.')

    _sql_constraints = [
        ('vin_uniq', 'unique(vin, company_id)', 'Ya existe un vehículo con ese número de chasis.'),
        ('odometer_positive', 'CHECK(odometer >= 0)', 'El kilometraje no puede ser negativo.'),
    ]

    @api.depends('model_id.name', 'model_id.brand_id.name', 'year', 'license_plate')
    def _compute_name(self):
        for vehicle in self:
            name = f'{vehicle.model_id.display_name or ""} {vehicle.year or ""}'.strip()
            if vehicle.license_plate:
                name += f' ({vehicle.license_plate})'
            vehicle.name = name

    def _compute_counts(self):
        for vehicle in self:
            vehicle.test_drive_count = len(vehicle.test_drive_ids)
            vehicle.workshop_order_count = len(vehicle.workshop_order_ids)
            vehicle.sale_order_count = len(vehicle.sale_order_ids)

    @api.depends('workshop_order_ids.state', 'workshop_order_ids.amount_total')
    def _compute_workshop_amount_total(self):
        for vehicle in self:
            finished = vehicle.workshop_order_ids.filtered(lambda order: order.state == 'done')
            vehicle.workshop_amount_total = sum(finished.mapped('amount_total'))

    @api.constrains('vin')
    def _check_vin(self):
        for vehicle in self:
            if not VIN_PATTERN.match(vehicle.vin or ''):
                raise ValidationError(
                    f'El número de chasis "{vehicle.vin}" no es válido: debe tener 17 letras o números '
                    'y no puede usar las letras I, O ni Q.')

    @api.constrains('year')
    def _check_year(self):
        next_year = fields.Date.today().year + 1
        for vehicle in self:
            if not 1900 <= vehicle.year <= next_year:
                raise ValidationError(f'El año {vehicle.year} no es válido.')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._normalize_vals(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._normalize_vals(vals)
        lowered = self._check_odometer_decrease(vals)
        res = super().write(vals)
        for vehicle, previous in lowered:
            vehicle.message_post(body=f'Kilometraje corregido a mano por {self.env.user.name}: '
                                      f'{previous} → {vehicle.odometer} km.')
        return res

    def _check_odometer_decrease(self, vals):
        """Bajar el kilometraje es una corrección: solo la hace un Responsable y queda en el historial.

        Devuelve [(vehículo, kilometraje anterior)] de los vehículos a los que se les baja.
        """
        if 'odometer' not in vals:
            return []
        odometer = vals['odometer'] or 0
        lowered = [(vehicle, vehicle.odometer) for vehicle in self if odometer < vehicle.odometer]
        if lowered and not self.env.su and not self.env.user.has_group('autoflow_management.group_autoflow_manager'):
            vehicle, previous = lowered[0]
            raise UserError(f'Solo un Responsable de AutoFlow puede bajar el kilometraje de {vehicle.display_name} '
                            f'({previous} → {odometer} km). Si el valor está mal, pídale que lo corrija.')
        return lowered

    @api.model
    def _normalize_vals(self, vals):
        # Chasis y chapa siempre en mayúsculas y sin espacios, así no se duplican por cómo se escribieron.
        for field_name in ('vin', 'license_plate'):
            if vals.get(field_name):
                vals[field_name] = vals[field_name].replace(' ', '').upper()

    def _update_odometer(self, odometer):
        """Sube el kilometraje del vehículo; nunca lo baja."""
        for vehicle in self:
            if odometer and odometer > vehicle.odometer:
                vehicle.odometer = odometer

    # Botones

    def action_reserve(self):
        for vehicle in self:
            if vehicle.state != 'available':
                raise UserError(f'Solo se puede reservar un vehículo disponible ({vehicle.display_name}).')
        self.state = 'reserved'

    def action_release(self):
        for vehicle in self:
            if vehicle.state != 'reserved':
                raise UserError(f'{vehicle.display_name} no está reservado.')
        self.state = 'available'

    def action_open_reception_wizard(self):
        self.ensure_one()
        return {
            'name': 'Recepción de vehículo',
            'type': 'ir.actions.act_window',
            'res_model': 'autoflow.vehicle.reception.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_vehicle_id': self.id,
                'default_partner_id': self.partner_id.id,
            },
        }

    def action_view_test_drives(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('autoflow_management.action_autoflow_test_drive')
        action['domain'] = [('vehicle_id', '=', self.id)]
        action['context'] = {'default_vehicle_id': self.id}
        return action

    def action_view_workshop_orders(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('autoflow_management.action_autoflow_workshop_order')
        action['domain'] = [('vehicle_id', '=', self.id)]
        action['context'] = {'default_vehicle_id': self.id, 'default_partner_id': self.partner_id.id}
        return action

    def action_view_sale_orders(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('sale.action_quotations_with_onboarding')
        action['domain'] = [('vehicle_id', '=', self.id)]
        action['context'] = {'default_vehicle_id': self.id}
        return action


class AutoflowVehiclePhoto(models.Model):
    _name = 'autoflow.vehicle.photo'
    _description = 'Foto de vehículo'
    _inherit = ['image.mixin']
    _order = 'sequence, id'

    name = fields.Char('Descripción', required=True, default='Foto')
    sequence = fields.Integer(default=10)
    vehicle_id = fields.Many2one('autoflow.vehicle', string='Vehículo', required=True,
                                 ondelete='cascade', index=True)
    image_1920 = fields.Image(required=True)
