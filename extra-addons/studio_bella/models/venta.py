# -*- coding: utf-8 -*-
from odoo import Command, api, fields, models
from odoo.exceptions import UserError

ESTADOS_VENTA = [
    ('borrador', 'Borrador'),
    ('cobrada', 'Cobrada'),
    ('cancelada', 'Cancelada'),
]


class BellaVenta(models.Model):
    """Venta de productos en el mostrador, sin cita (por ejemplo, alguien que pasa a comprar un shampoo)."""
    _name = 'bella.venta'
    _description = 'Venta de productos'
    _inherit = ['bella.cobro.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'fecha desc, id desc'
    _check_company_auto = True

    name = fields.Char('Número', readonly=True, copy=False, default='Nuevo')
    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                 default=lambda self: self.env.company)
    fecha = fields.Datetime('Fecha', required=True, default=fields.Datetime.now)
    cliente_id = fields.Many2one('res.partner', string='Cliente', required=True, tracking=True, index=True,
                                 check_company=True, default=lambda self: self._default_cliente())
    vendedor_id = fields.Many2one('res.users', string='Vendedor', default=lambda self: self.env.user)
    estado = fields.Selection(ESTADOS_VENTA, string='Estado', default='borrador', required=True, readonly=True,
                              tracking=True, copy=False)
    linea_ids = fields.One2many('bella.venta.linea', 'venta_id', string='Productos', copy=True)
    nota = fields.Text('Notas')
    currency_id = fields.Many2one(related='company_id.currency_id')
    total = fields.Monetary('Total', compute='_compute_total', store=True, tracking=True)

    @api.model
    def _default_cliente(self):
        return self.env.ref('studio_bella.cliente_consumidor_final', raise_if_not_found=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code('bella.venta') or 'Nuevo'
        return super().create(vals_list)

    @api.ondelete(at_uninstall=False)
    def _unlink_excepto_cobradas(self):
        if any(venta.estado == 'cobrada' for venta in self):
            raise UserError('No se puede eliminar una venta cobrada: tiene una factura emitida.')

    @api.depends('linea_ids.subtotal')
    def _compute_total(self):
        for venta in self:
            venta.total = sum(venta.linea_ids.mapped('subtotal'))

    # Cobro (ver bella.cobro.mixin)

    def _bella_cobrar(self, metodo_pago, diario=None, fecha=None, puntos=0):
        if self.estado != 'borrador':
            raise UserError(f'La venta {self.name} no está en borrador.')
        factura = super()._bella_cobrar(metodo_pago, diario=diario, fecha=fecha, puntos=puntos)
        self.estado = 'cobrada'
        return factura

    def _bella_lineas_factura(self):
        return [Command.create(linea._bella_valores_linea_factura()) for linea in self.linea_ids]

    def _bella_productos_vendidos(self):
        return self.linea_ids

    # Botones

    def action_cobrar(self):
        self.ensure_one()
        if self.estado != 'borrador':
            raise UserError(f'La venta {self.name} no está en borrador.')
        if not self.linea_ids:
            raise UserError('Agregue al menos un producto antes de cobrar.')
        return {
            'type': 'ir.actions.act_window',
            'name': f'Cobrar {self.name}',
            'res_model': 'bella.cobro.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_venta_id': self.id},
        }

    def action_cancelar(self):
        if any(venta.estado == 'cobrada' for venta in self):
            raise UserError('Una venta cobrada no se cancela: emita una nota de crédito desde su factura.')
        self.estado = 'cancelada'
        return True

    def action_borrador(self):
        self.filtered(lambda venta: venta.estado == 'cancelada').estado = 'borrador'
        return True


class BellaVentaLinea(models.Model):
    _name = 'bella.venta.linea'
    _inherit = 'bella.linea.producto'
    _description = 'Producto de la venta'
    _order = 'venta_id, sequence, id'
    _check_company_auto = True

    venta_id = fields.Many2one('bella.venta', string='Venta', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='venta_id.company_id', store=True)
    currency_id = fields.Many2one(related='venta_id.currency_id')
