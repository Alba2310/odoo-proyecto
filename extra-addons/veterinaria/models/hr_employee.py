# -*- coding: utf-8 -*-
from odoo import fields, models

ATIENDE = [
    ('consultorio', 'Consultorio'),
    ('estetica', 'Baño y peluquería'),
    ('ambas', 'Consultorio y peluquería'),
]


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    vet_atiende = fields.Selection(ATIENDE, string='Atiende en Patitas',
                                   help='Aparece en esa agenda y se le pueden dar turnos.')
    vet_matricula = fields.Char('Matrícula profesional', help='Sale debajo de la firma en las indicaciones.')
    # groups: quien no administra empleados los lee a través de hr.employee.public, que no tiene este campo.
    # Las validaciones de la atención lo leen con sudo().
    vet_servicio_ids = fields.Many2many('product.product', string='Servicios que hace',
                                        domain=[('vet_area', 'in', ('consultorio', 'estetica'))],
                                        groups='hr.group_hr_user',
                                        help='Si se deja vacío, hace todos los de su área.')

    def _vet_hace(self, area):
        """Atiende en esa área (consultorio o baño y peluquería)."""
        self.ensure_one()
        return self.vet_atiende in (area, 'ambas')


class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    # El personal tiene que poder elegir profesionales sin ver los datos privados de los empleados.
    vet_atiende = fields.Selection(ATIENDE, readonly=True)
    vet_matricula = fields.Char(readonly=True)
