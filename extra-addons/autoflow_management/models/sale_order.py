# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    vehicle_id = fields.Many2one('autoflow.vehicle', string='Vehículo', check_company=True,
                                 domain="[('state', '!=', 'sold')]", index='btree_not_null',
                                 help='Vehículo que se vende. Al confirmar el pedido queda como vendido.')
    test_drive_id = fields.Many2one('autoflow.test.drive', string='Prueba de manejo', readonly=True,
                                    copy=False, index='btree_not_null')

    def action_confirm(self):
        for order in self.filtered('vehicle_id'):
            if order.vehicle_id.state == 'sold':
                raise UserError(f'{order.vehicle_id.display_name} ya está vendido.')
        res = super().action_confirm()
        # sudo: un vendedor sin acceso al taller igual puede vender el vehículo.
        for order in self.filtered('vehicle_id'):
            order.vehicle_id.sudo().write({'state': 'sold', 'partner_id': order.partner_id.id})
        return res

    def _action_cancel(self):
        # Si se cancela una venta confirmada, el vehículo vuelve a estar disponible.
        sold = self.filtered(lambda order: order.state == 'sale' and order.vehicle_id.state == 'sold')
        res = super()._action_cancel()
        sold.vehicle_id.sudo().write({'state': 'available', 'partner_id': False})
        return res
