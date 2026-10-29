# -*- coding: utf-8 -*-
from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    bella_estilista = fields.Boolean('Atiende en Studio Bella',
                                     help='Aparece en la agenda y se le pueden asignar citas.')
    # groups: los usuarios sin permisos de Empleados leen los empleados a través de hr.employee.public,
    # que no tiene este campo. Las validaciones de la cita lo leen con sudo().
    bella_servicio_ids = fields.Many2many('product.product', string='Servicios que realiza',
                                          domain=[('type', '=', 'service')], groups='hr.group_hr_user',
                                          help='Si se deja vacío, puede hacer todos los servicios.')
    bella_comision_servicios = fields.Float('% de comisión por servicios', groups='hr.group_hr_user',
                                            help='Sobre el precio cobrado (IVA incluido) de los servicios que hace.')
    bella_comision_productos = fields.Float('% de comisión por productos', groups='hr.group_hr_user',
                                            help='Sobre lo cobrado (IVA incluido) por los productos que vende en '
                                                 'sus citas.')


class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    # La recepción tiene que poder elegir estilistas sin tener acceso a los datos privados de los empleados.
    bella_estilista = fields.Boolean(readonly=True)
