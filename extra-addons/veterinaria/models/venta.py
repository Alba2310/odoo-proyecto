# -*- coding: utf-8 -*-
from odoo import Command, api, fields, models
from odoo.exceptions import UserError

ESTADOS_VENTA = [
    ('borrador', 'Abierta'),
    ('cobrada', 'Cobrada'),
    ('cancelada', 'Cancelada'),
]


class VetVenta(models.Model):
    """Venta en el mostrador, sin mascota de por medio: una bolsa de alimento, una pipeta, un collar."""
    _name = 'vet.venta'
    _description = 'Venta de mostrador'
    _inherit = ['vet.cobrable', 'mail.thread']
    _order = 'fecha desc, id desc'
    _check_company_auto = True

    name = fields.Char('Número', readonly=True, copy=False, default='Nuevo')
    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                 default=lambda self: self.env.company)
    fecha = fields.Datetime('Fecha', required=True, default=fields.Datetime.now)
    dueno_id = fields.Many2one('res.partner', string='Cliente', required=True, tracking=True, index=True,
                               check_company=True, default=lambda self: self._default_cliente())
    vendedor_id = fields.Many2one('res.users', string='Vendió', default=lambda self: self.env.user)
    estado = fields.Selection(ESTADOS_VENTA, string='Estado', default='borrador', required=True, readonly=True,
                              tracking=True, copy=False)
    linea_ids = fields.One2many('vet.venta.linea', 'venta_id', string='Productos', copy=True)
    nota = fields.Text('Notas')
    currency_id = fields.Many2one(related='company_id.currency_id')
    total = fields.Monetary('Total', compute='_compute_total', store=True, tracking=True)

    @api.model
    def _default_cliente(self):
        return self.env.ref('veterinaria.cliente_consumidor_final', raise_if_not_found=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code('vet.venta') or 'Nuevo'
        return super().create(vals_list)

    @api.ondelete(at_uninstall=False)
    def _unlink_excepto_cobradas(self):
        if any(venta.estado == 'cobrada' for venta in self):
            raise UserError('No se puede borrar una venta cobrada: tiene una factura emitida.')

    @api.depends('linea_ids.subtotal')
    def _compute_total(self):
        for venta in self:
            venta.total = sum(venta.linea_ids.mapped('subtotal'))

    # Cobro (ver vet.cobrable)

    def _vet_cobrar(self, pagos, fecha=None):
        self.ensure_one()
        if self.estado != 'borrador':
            raise UserError(f'La venta {self.name} no está abierta.')
        factura = super()._vet_cobrar(pagos, fecha=fecha)
        self.estado = 'cobrada'
        return factura

    def _vet_lineas_factura(self):
        return [Command.create(linea._vet_valores_factura()) for linea in self.linea_ids]

    def _vet_lineas_vendidas(self):
        return self.linea_ids

    # Botones

    def action_cobrar(self):
        self.ensure_one()
        if self.estado != 'borrador':
            raise UserError(f'La venta {self.name} no está abierta.')
        if not self.linea_ids:
            raise UserError('Agregue al menos un producto antes de cobrar.')
        return self._vet_abrir_cobro('venta_id')

    def action_cancelar(self):
        if any(venta.estado == 'cobrada' for venta in self):
            raise UserError('Una venta cobrada no se cancela: emita una nota de crédito desde su factura.')
        self.estado = 'cancelada'
        return True

    def action_reabrir(self):
        self.filtered(lambda venta: venta.estado == 'cancelada').estado = 'borrador'
        return True


class VetVentaLinea(models.Model):
    _name = 'vet.venta.linea'
    _inherit = 'vet.linea.venta'
    _description = 'Producto de la venta de mostrador'
    _order = 'venta_id, sequence, id'
    _check_company_auto = True

    venta_id = fields.Many2one('vet.venta', string='Venta', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='venta_id.company_id', store=True)
    currency_id = fields.Many2one(related='venta_id.currency_id')

    def _vet_documento(self):
        return self.venta_id
