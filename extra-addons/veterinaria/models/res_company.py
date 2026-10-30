# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    vet_url_reserva = fields.Char(
        'Página de turnos',
        help='Dirección pública de la página de turnos, para los mensajes a los dueños. '
             'Si se deja vacía, se usa la dirección de Odoo seguida de /reservar.')
    vet_dias_aviso_vacuna = fields.Integer(
        'Avisar las vacunas con', default=7,
        help='Días de anticipación con que el correo avisa al dueño que se acerca la próxima dosis.')
    vet_horas_control = fields.Integer(
        'Control de internados cada', default=8,
        help='Horas: si un internado pasa más tiempo sin control, el tablero lo marca en rojo.')
    vet_producto_internacion_id = fields.Many2one(
        'product.product', string='Día de internación', domain=[('vet_area', '=', 'internacion')],
        help='Lo que se cobra por cada día de internación.')
    vet_producto_hotel_id = fields.Many2one(
        'product.product', string='Día de hotel', domain=[('vet_area', '=', 'internacion')],
        help='Lo que se cobra por cada día de hotel o guardería.')
    vet_diario_efectivo_id = fields.Many2one('account.journal', string='Diario del efectivo',
                                             domain=[('type', '=', 'cash')])
    vet_diario_tarjeta_id = fields.Many2one('account.journal', string='Diario de las tarjetas',
                                            domain=[('type', '=', 'bank')])
    vet_diario_transferencia_id = fields.Many2one('account.journal', string='Diario de las transferencias',
                                                  domain=[('type', '=', 'bank')])

    def _vet_url_reserva(self):
        self.ensure_one()
        return self.vet_url_reserva or f'{self.get_base_url()}/reservar'
