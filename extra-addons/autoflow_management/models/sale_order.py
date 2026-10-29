# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.exceptions import UserError

from .workshop_order import OPEN_STATES


def _open_workshop_order(vehicle):
    """Orden de servicio abierta del vehículo, si está en el taller.

    sudo: un vendedor no ve las órdenes de servicio. Mientras el vehículo está en el taller figura
    "En mantenimiento" y el estado que tenía antes (por ejemplo, vendido) queda guardado en la orden.
    """
    return vehicle.sudo().workshop_order_ids.filtered(lambda order: order.state in OPEN_STATES)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    vehicle_id = fields.Many2one('autoflow.vehicle', string='Vehículo', check_company=True,
                                 domain="[('state', '!=', 'sold')]", index='btree_not_null',
                                 help='Vehículo que se vende. Al confirmar el pedido queda como vendido.')
    test_drive_id = fields.Many2one('autoflow.test.drive', string='Prueba de manejo', readonly=True,
                                    copy=False, index='btree_not_null')

    def action_confirm(self):
        for order in self.filtered('vehicle_id'):
            vehicle = order.vehicle_id
            if 'sold' in (vehicle.state, _open_workshop_order(vehicle).vehicle_previous_state):
                raise UserError(f'{vehicle.display_name} ya está vendido.')
        res = super().action_confirm()
        # sudo: un vendedor sin acceso al taller igual puede vender el vehículo.
        for order in self.filtered('vehicle_id'):
            order.vehicle_id.sudo().write({'state': 'sold', 'partner_id': order.partner_id.id})
        return res

    def _action_cancel(self):
        # Si se cancela una venta confirmada, el vehículo vuelve a estar disponible. Si está en el taller,
        # sigue en mantenimiento y queda disponible cuando sale.
        vehicles = self.filtered(lambda order: order.state == 'sale').vehicle_id.sudo()
        res = super()._action_cancel()
        for vehicle in vehicles:
            workshop_order = _open_workshop_order(vehicle)
            if workshop_order:
                # Vendido antes de entrar al taller (quedó guardado en la orden) o mientras estaba ahí.
                if 'sold' in (vehicle.state, workshop_order.vehicle_previous_state):
                    workshop_order.vehicle_previous_state = 'available'
                    vehicle.write({'state': 'maintenance', 'partner_id': False})
            elif vehicle.state == 'sold':
                vehicle.write({'state': 'available', 'partner_id': False})
        return res
