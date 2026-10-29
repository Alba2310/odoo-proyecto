# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    bella_url_turnos = fields.Char(
        'Página de turnos',
        help='Dirección pública de la página de turnos, para el mensaje que invita a volver a las clientas. '
             'Si se deja vacía, se usa la dirección de Odoo seguida de /turnos.')

    # Programa de puntos: 1 punto cada 10.000 Gs. pagados y cada punto vale 500 Gs. de descuento (5 %).
    bella_puntos_activo = fields.Boolean('Programa de puntos')
    bella_puntos_monto = fields.Monetary('Monto por punto', default=10000,
                                         help='La clienta gana un punto por cada este monto que paga.')
    bella_puntos_valor = fields.Monetary('Valor del punto', default=500,
                                         help='Descuento que vale cada punto al usarlo en un cobro.')

    def _bella_url_turnos(self):
        self.ensure_one()
        return self.bella_url_turnos or f'{self.get_base_url()}/turnos'
