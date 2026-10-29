# -*- coding: utf-8 -*-
from collections import defaultdict

from markupsafe import Markup

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare

from .vehicle import VEHICLE_STATES

ORDER_STATES = [
    ('received', 'Recibido'),
    ('diagnosis', 'En diagnóstico'),
    ('waiting_parts', 'Esperando repuestos'),
    ('repair', 'En reparación'),
    ('ready', 'Listo para entrega'),
    ('done', 'Finalizado'),
    ('cancel', 'Cancelado'),
]
# Mientras la orden está en alguna de estas etapas, el vehículo está en el taller.
OPEN_STATES = ('received', 'diagnosis', 'waiting_parts', 'repair', 'ready')

SERVICE_TYPES = [
    ('preventive', 'Preventivo'),
    ('corrective', 'Correctivo'),
    ('warranty', 'Garantía'),
]


class AutoflowWorkshopOrder(models.Model):
    _name = 'autoflow.workshop.order'
    _description = 'Orden de servicio'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, date_received desc, id desc'
    _check_company_auto = True

    name = fields.Char('Número', readonly=True, copy=False, default='Nuevo')
    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                 default=lambda self: self.env.company)
    partner_id = fields.Many2one('res.partner', string='Cliente', required=True, tracking=True,
                                 check_company=True)
    vehicle_id = fields.Many2one('autoflow.vehicle', string='Vehículo', required=True, tracking=True,
                                 check_company=True)
    # Guardados en la orden para poder agrupar el análisis por modelo y marca.
    vehicle_model_id = fields.Many2one(related='vehicle_id.model_id', store=True, string='Modelo')
    vehicle_brand_id = fields.Many2one(related='vehicle_id.brand_id', store=True, string='Marca')
    vehicle_vin = fields.Char(related='vehicle_id.vin', string='Chasis (VIN)')
    vehicle_image = fields.Image(related='vehicle_id.image_128')
    service_type = fields.Selection(SERVICE_TYPES, string='Tipo de servicio', required=True,
                                    default='preventive', tracking=True)
    mechanic_id = fields.Many2one('hr.employee', string='Mecánico', tracking=True, check_company=True)
    user_id = fields.Many2one('res.users', string='Asesor de servicio', tracking=True,
                              default=lambda self: self.env.user)
    state = fields.Selection(ORDER_STATES, string='Etapa', default='received', required=True,
                             tracking=True, copy=False, group_expand='_group_expand_states')
    priority = fields.Selection([('0', 'Normal'), ('1', 'Urgente')], string='Prioridad', default='0')
    date_received = fields.Datetime('Fecha de ingreso', required=True, default=fields.Datetime.now)
    date_promised = fields.Datetime('Entrega prometida')
    date_done = fields.Datetime('Fecha de cierre', readonly=True, copy=False)
    warehouse_id = fields.Many2one('stock.warehouse', string='Depósito de repuestos', required=True,
                                   check_company=True, default=lambda self: self._default_warehouse())

    # Recepción
    odometer = fields.Integer('Kilometraje', tracking=True)
    fuel_level = fields.Integer('Combustible al ingreso (%)')
    damage_ids = fields.Many2many('autoflow.damage.type', string='Daños visibles al ingreso')
    customer_complaint = fields.Text('Motivo de ingreso')
    diagnosis = fields.Text('Diagnóstico')
    # Estado que tenía el vehículo antes de entrar al taller, para devolvérselo al salir.
    vehicle_previous_state = fields.Selection(VEHICLE_STATES, copy=False)

    # Trabajo
    part_line_ids = fields.One2many('autoflow.workshop.part.line', 'order_id', string='Repuestos', copy=True)
    labor_line_ids = fields.One2many('autoflow.workshop.labor.line', 'order_id', string='Mano de obra',
                                     copy=True)
    inspection_line_ids = fields.One2many('autoflow.inspection.line', 'order_id', string='Checklist de entrega',
                                          default=lambda self: self._default_inspection_lines())
    inspection_pending_count = fields.Integer(compute='_compute_inspection_pending_count')
    parts_available = fields.Boolean('Repuestos disponibles', compute='_compute_parts_available')
    stock_move_ids = fields.One2many('stock.move', 'autoflow_order_id', string='Movimientos de stock')

    # Costos
    currency_id = fields.Many2one(related='company_id.currency_id')
    labor_hours = fields.Float('Horas de mano de obra', compute='_compute_amounts', store=True)
    amount_labor = fields.Monetary('Total mano de obra', compute='_compute_amounts', store=True)
    amount_parts = fields.Monetary('Total repuestos', compute='_compute_amounts', store=True)
    amount_total = fields.Monetary('Total', compute='_compute_amounts', store=True, tracking=True)
    invoice_id = fields.Many2one('account.move', string='Factura', readonly=True, copy=False,
                                 groups='account.group_account_invoice')
    payment_state = fields.Selection(related='invoice_id.payment_state', string='Estado de pago',
                                     groups='account.group_account_invoice')

    # Acta de entrega
    customer_signature = fields.Binary('Firma del cliente', copy=False, attachment=True)
    signed_by = fields.Char('Firmado por', copy=False)
    signed_on = fields.Datetime('Firmado el', copy=False, readonly=True)

    _sql_constraints = [
        ('odometer_positive', 'CHECK(odometer >= 0)', 'El kilometraje no puede ser negativo.'),
    ]

    @api.model
    def _default_warehouse(self):
        return self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)

    @api.model
    def _default_inspection_lines(self):
        # Cada orden nueva arranca con todos los puntos del checklist sin revisar.
        items = self.env['autoflow.inspection.item'].search([])
        return [Command.create({'item_id': item.id}) for item in items]

    def _group_expand_states(self, states, domain):
        # El kanban muestra todas las etapas aunque estén vacías; las canceladas solo si hay.
        return [state for state, _label in ORDER_STATES if state != 'cancel']

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code('autoflow.workshop.order') or 'Nuevo'
            if vals.get('customer_signature'):
                vals['signed_on'] = fields.Datetime.now()
        orders = super().create(vals_list)
        orders.filtered(lambda order: order.state in OPEN_STATES)._set_vehicle_in_workshop()
        return orders

    def write(self, vals):
        if 'vehicle_id' in vals and any(order.vehicle_id.id != vals['vehicle_id'] for order in self):
            raise UserError('No se puede cambiar el vehículo de una orden ya creada. '
                            'Cancélela y cree una nueva para el otro vehículo.')
        if vals.get('customer_signature'):
            vals = dict(vals, signed_on=fields.Datetime.now())
        new_state = vals.get('state')
        if not new_state:
            return super().write(vals)

        # Cambio de etapa: desde los botones, la barra de estado o arrastrando la tarjeta en el kanban.
        changed = self.filtered(lambda order: order.state != new_state)
        changed._check_state_change(new_state)
        reopened = changed.filtered(lambda order: order.state == 'cancel')
        if new_state == 'done':
            # La barra de estado manda en la misma escritura los cambios del formulario que no se guardaron
            # (un repuesto nuevo, el mecánico...): se guardan primero y se valida la orden como va a quedar.
            other_vals = {key: value for key, value in vals.items() if key != 'state'}
            if other_vals:
                super().write(other_vals)
                vals = {'state': new_state}
            for order in changed:
                order._check_can_finish()
        res = super().write(vals)
        if new_state == 'ready':
            changed._notify_vehicle_ready()
        elif new_state == 'done':
            changed.date_done = fields.Datetime.now()
            changed._finish()
        elif new_state == 'cancel':
            changed._release_vehicle()
        reopened._set_vehicle_in_workshop()
        return res

    @api.ondelete(at_uninstall=False)
    def _unlink_except_done(self):
        if any(order.state == 'done' for order in self):
            raise UserError('No se puede eliminar una orden finalizada.')

    def unlink(self):
        self.filtered(lambda order: order.state in OPEN_STATES)._release_vehicle()
        return super().unlink()

    # Campos computados

    @api.depends('part_line_ids.price_subtotal', 'labor_line_ids.price_subtotal', 'labor_line_ids.hours')
    def _compute_amounts(self):
        for order in self:
            order.labor_hours = sum(order.labor_line_ids.mapped('hours'))
            order.amount_labor = sum(order.labor_line_ids.mapped('price_subtotal'))
            order.amount_parts = sum(order.part_line_ids.mapped('price_subtotal'))
            order.amount_total = order.amount_labor + order.amount_parts

    @api.depends('inspection_line_ids.state')
    def _compute_inspection_pending_count(self):
        for order in self:
            order.inspection_pending_count = len(
                order.inspection_line_ids.filtered(lambda line: line.state == 'pending'))

    @api.depends('part_line_ids.qty_available', 'part_line_ids.quantity', 'part_line_ids.move_id')
    def _compute_parts_available(self):
        for order in self:
            order.parts_available = not order._get_missing_parts()

    def _get_missing_parts(self):
        """Repuestos con seguimiento de stock que todavía no se descontaron y no alcanzan.

        Devuelve {producto: (cantidad necesaria, cantidad en depósito)}. Se suma por producto: dos líneas
        de 6 del mismo repuesto con 10 en el depósito no alcanzan.
        """
        self.ensure_one()
        needed = defaultdict(float)
        available = {}
        for line in self.part_line_ids.filtered(lambda line: line.product_id.is_storable and not line.move_id):
            needed[line.product_id] += line.quantity
            available[line.product_id] = line.qty_available
        return {
            product: (quantity, available[product])
            for product, quantity in needed.items()
            if float_compare(available[product], quantity, precision_rounding=product.uom_id.rounding) < 0
        }

    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        if self.vehicle_id:
            self.odometer = max(self.odometer, self.vehicle_id.odometer)
            if self.vehicle_id.partner_id:
                self.partner_id = self.vehicle_id.partner_id

    # Restricciones

    @api.constrains('vehicle_id', 'state')
    def _check_single_open_order(self):
        for order in self.filtered(lambda o: o.state in OPEN_STATES):
            other = self.search([
                ('id', '!=', order.id),
                ('vehicle_id', '=', order.vehicle_id.id),
                ('state', 'in', OPEN_STATES),
            ], limit=1)
            if other:
                raise ValidationError(
                    f'{order.vehicle_id.display_name} ya está en el taller con la orden {other.name}.')

    @api.constrains('fuel_level')
    def _check_fuel_level(self):
        for order in self:
            if not 0 <= order.fuel_level <= 100:
                raise ValidationError('El nivel de combustible debe estar entre 0 y 100 %.')

    def _check_state_change(self, new_state):
        for order in self:
            if order.state == 'done':
                raise UserError(f'La orden {order.name} ya está finalizada; no se puede cambiar de etapa.')
            if order.state == 'cancel' and new_state != 'received':
                raise UserError(f'La orden {order.name} está cancelada. Reábrala antes de moverla.')

    def _check_can_finish(self):
        self.ensure_one()
        problems = []
        if not self.mechanic_id:
            problems.append('Asigne el mecánico responsable.')
        if not self.part_line_ids and not self.labor_line_ids:
            problems.append('Cargue la mano de obra o los repuestos utilizados.')
        if self.inspection_pending_count:
            problems.append(f'Faltan revisar {self.inspection_pending_count} puntos del checklist de entrega.')
        for product, (needed, available) in self._get_missing_parts().items():
            problems.append(f'No hay stock de {product.display_name}: se necesitan {needed:g} '
                            f'y en {self.warehouse_id.name} hay {available:g}.')
        if problems:
            raise UserError(f'No se puede finalizar la orden {self.name}:\n• ' + '\n• '.join(problems))

    # Flujo del taller

    def _set_vehicle_in_workshop(self):
        for order in self:
            vehicle = order.vehicle_id
            if vehicle.state != 'maintenance':
                order.vehicle_previous_state = vehicle.state
                vehicle.state = 'maintenance'

    def _release_vehicle(self):
        """Devuelve el vehículo al estado que tenía antes de entrar al taller."""
        for order in self:
            if order.vehicle_id.state == 'maintenance':
                order.vehicle_id.state = order.vehicle_previous_state or 'available'

    def _notify_vehicle_ready(self):
        """Avisa al cliente por correo y deja una actividad al asesor para coordinar la entrega."""
        template = self.env.ref('autoflow_management.mail_template_vehicle_ready')
        for order in self:
            order.message_post_with_source(template, subtype_xmlid='mail.mt_comment')
            order.activity_schedule(
                'mail.mail_activity_data_todo',
                summary='Coordinar la entrega del vehículo',
                note=f'{order.vehicle_id.display_name} está listo para entregar a {order.partner_id.name}.',
                user_id=order.user_id.id or self.env.uid,
            )

    def _finish(self):
        """Entrega del vehículo: descuenta repuestos, actualiza el kilometraje y factura."""
        for order in self:
            order._consume_parts()
            order.vehicle_id._update_odometer(order.odometer)
            order._release_vehicle()
            order._create_invoice()

    def _consume_parts(self):
        """Saca del depósito los repuestos usados con movimientos de stock de Odoo."""
        self.ensure_one()
        lines = self.part_line_ids.filtered(lambda line: line.product_id.type == 'consu' and not line.move_id)
        if not lines:
            return
        destination = (self.partner_id.property_stock_customer
                       or self.env.ref('stock.stock_location_customers'))
        moves = self.env['stock.move'].create([{
            'name': f'{self.name}: {line.product_id.display_name}',
            'origin': self.name,
            'product_id': line.product_id.id,
            'product_uom': line.product_uom_id.id,
            'product_uom_qty': line.quantity,
            'location_id': self.warehouse_id.lot_stock_id.id,
            'location_dest_id': destination.id,
            'partner_id': self.partner_id.id,
            'company_id': self.company_id.id,
            'autoflow_order_id': self.id,
        } for line in lines])
        for line, move in zip(lines, moves):
            line.move_id = move
        moves._action_confirm()
        moves._action_assign()
        for move in moves:
            move.quantity = move.product_uom_qty
        moves.picked = True
        moves._action_done()

    def _create_invoice(self):
        # sudo: el mecánico o el asesor que entrega el vehículo no necesita permisos de facturación;
        # la factura queda en borrador para que la revise y la confirme contabilidad.
        for order in self.sudo().filtered(lambda o: not o.invoice_id):
            if order.service_type == 'warranty':
                order.message_post(body='Orden en garantía: no se factura al cliente.')
                continue
            invoice = self.env['account.move'].sudo().with_company(order.company_id).create(
                order._prepare_invoice_vals())
            order.invoice_id = invoice
            order.message_post(body=Markup('Se creó la factura en borrador %s.') % invoice._get_html_link())

    def _prepare_invoice_vals(self):
        self.ensure_one()
        labor_product = self.env.ref('autoflow_management.product_workshop_labor')
        vehicle = self.vehicle_id
        lines = [Command.create({
            'display_type': 'line_section',
            'name': f'{self.name} · {vehicle.display_name} · Chasis {vehicle.vin} · {self.odometer} km',
        })]
        lines += [Command.create({
            'product_id': labor_product.id,
            'name': f'Mano de obra: {line.name}',
            'quantity': line.hours,
            'price_unit': line.price_unit,
        }) for line in self.labor_line_ids]
        lines += [Command.create({
            'product_id': line.product_id.id,
            'quantity': line.quantity,
            'product_uom_id': line.product_uom_id.id,
            'price_unit': line.price_unit,
        }) for line in self.part_line_ids]
        return {
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'invoice_origin': self.name,
            'invoice_user_id': self.user_id.id,
            'company_id': self.company_id.id,
            'invoice_line_ids': lines,
        }

    # Botones

    def action_diagnosis(self):
        self.state = 'diagnosis'
        return True

    def action_waiting_parts(self):
        self.state = 'waiting_parts'
        return True

    def action_repair(self):
        self.state = 'repair'
        return True

    def action_ready(self):
        self.state = 'ready'
        return True

    def action_done(self):
        self.state = 'done'
        return True

    def action_cancel(self):
        self.state = 'cancel'
        return True

    def action_reopen(self):
        self.state = 'received'
        return True

    def action_inspection_mark_ok(self):
        """Marca como OK los puntos del checklist que siguen sin revisar."""
        self.inspection_line_ids.filtered(lambda line: line.state == 'pending').state = 'ok'
        return True

    def action_view_invoice(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Factura',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
        }

    def action_view_stock_moves(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('stock.stock_move_action')
        action['domain'] = [('autoflow_order_id', '=', self.id)]
        action['context'] = {'create': False}
        return action


class AutoflowWorkshopPartLine(models.Model):
    _name = 'autoflow.workshop.part.line'
    _description = 'Repuesto de orden de servicio'
    _order = 'order_id, sequence, id'
    _check_company_auto = True

    order_id = fields.Many2one('autoflow.workshop.order', string='Orden de servicio', required=True,
                               ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(related='order_id.company_id', store=True)
    product_id = fields.Many2one('product.product', string='Repuesto', required=True, check_company=True,
                                 domain=lambda self: self._domain_workshop_parts())
    quantity = fields.Float('Cantidad', default=1, required=True, digits='Product Unit of Measure')
    product_uom_id = fields.Many2one(related='product_id.uom_id', string='Unidad')
    is_storable = fields.Boolean(related='product_id.is_storable')
    qty_available = fields.Float('En depósito', compute='_compute_qty_available',
                                 digits='Product Unit of Measure')
    currency_id = fields.Many2one(related='order_id.currency_id')
    price_unit = fields.Monetary('Precio unitario', compute='_compute_price_unit',
                                 store=True, readonly=False, precompute=True)
    price_subtotal = fields.Monetary('Subtotal', compute='_compute_price_subtotal', store=True)
    move_id = fields.Many2one('stock.move', string='Movimiento de stock', readonly=True, copy=False)

    _sql_constraints = [
        ('quantity_positive', 'CHECK(quantity > 0)', 'La cantidad de repuestos debe ser mayor que cero.'),
    ]

    @api.model
    def _domain_workshop_parts(self):
        # Al cargar repuestos solo se ofrecen los del catálogo del taller, no cualquier producto de la empresa.
        domain = [('type', '=', 'consu')]
        category = self.env.ref('autoflow_management.product_category_workshop', raise_if_not_found=False)
        return domain + [('categ_id', 'child_of', category.id)] if category else domain

    @api.depends('product_id', 'order_id.warehouse_id')
    def _compute_qty_available(self):
        for line in self:
            location = line.order_id.warehouse_id.lot_stock_id
            product = line.product_id.with_context(location=location.id) if location else line.product_id
            line.qty_available = product.qty_available

    @api.depends('product_id')
    def _compute_price_unit(self):
        for line in self:
            line.price_unit = line.product_id.lst_price

    @api.depends('quantity', 'price_unit')
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit


class AutoflowWorkshopLaborLine(models.Model):
    _name = 'autoflow.workshop.labor.line'
    _description = 'Mano de obra de orden de servicio'
    _order = 'order_id, sequence, id'
    _check_company_auto = True

    order_id = fields.Many2one('autoflow.workshop.order', string='Orden de servicio', required=True,
                               ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(related='order_id.company_id', store=True)
    name = fields.Char('Trabajo realizado', required=True)
    employee_id = fields.Many2one('hr.employee', string='Mecánico', check_company=True,
                                  compute='_compute_employee_id', store=True, readonly=False, precompute=True)
    # Con la misma precisión que la cantidad de la factura (0:20 h se guarda como 0,33 h), así el subtotal
    # de la orden y el del PDF dan lo mismo que la factura.
    hours = fields.Float('Horas', default=1, required=True, digits='Product Unit of Measure')
    currency_id = fields.Many2one(related='order_id.currency_id')
    price_unit = fields.Monetary('Precio por hora', compute='_compute_price_unit',
                                 store=True, readonly=False, precompute=True)
    price_subtotal = fields.Monetary('Subtotal', compute='_compute_price_subtotal', store=True)

    _sql_constraints = [
        ('hours_positive', 'CHECK(hours > 0)', 'Las horas de mano de obra deben ser mayores que cero.'),
    ]

    @api.depends('order_id.mechanic_id')
    def _compute_employee_id(self):
        for line in self:
            if not line.employee_id:
                line.employee_id = line.order_id.mechanic_id

    @api.depends('order_id')
    def _compute_price_unit(self):
        # La tarifa por hora sale del producto "Mano de obra de taller"; se puede cambiar por línea.
        labor_product = self.env.ref('autoflow_management.product_workshop_labor', raise_if_not_found=False)
        for line in self:
            if not line.price_unit:
                line.price_unit = labor_product.lst_price if labor_product else 0

    @api.depends('hours', 'price_unit')
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.hours * line.price_unit
