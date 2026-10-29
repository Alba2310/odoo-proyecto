# -*- coding: utf-8 -*-
from odoo import fields, models


class BellaPuntos(models.Model):
    """Movimiento de puntos de una clienta: los gana al pagar y los usa como descuento en otro cobro.

    El saldo es la suma de los movimientos. Los del cobro los crea el sistema; Administración puede cargar otros a
    mano (un regalo de cumpleaños, una corrección).
    """
    _name = 'bella.puntos'
    _description = 'Movimiento de puntos'
    _order = 'fecha desc, id desc'
    _check_company_auto = True

    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                 default=lambda self: self.env.company)
    cliente_id = fields.Many2one('res.partner', string='Cliente', required=True, index=True, check_company=True)
    fecha = fields.Date('Fecha', required=True, default=fields.Date.context_today)
    puntos = fields.Integer('Puntos', required=True, help='Positivos: ganados o regalados. Negativos: usados.')
    concepto = fields.Char('Concepto', required=True)
    factura_id = fields.Many2one('account.move', string='Factura', readonly=True, check_company=True)
