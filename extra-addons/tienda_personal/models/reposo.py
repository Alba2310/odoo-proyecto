# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class TiendaReposo(models.Model):
    """Reposo (por ejemplo, médico): los días que cubre no son faltas, no se pagan
    y no le quitan el bono al empleado."""
    _name = 'tienda.reposo'
    _description = 'Reposo'
    _order = 'desde desc'

    empleado_id = fields.Many2one('tienda.empleado', string='Empleado', required=True,
                                  ondelete='cascade', index=True)
    sucursal_id = fields.Many2one(related='empleado_id.sucursal_id', store=True, string='Sucursal')
    desde = fields.Date('Desde', required=True, default=fields.Date.context_today)
    hasta = fields.Date('Hasta', required=True, default=fields.Date.context_today)
    dias = fields.Integer('Días', compute='_compute_dias', store=True)
    motivo = fields.Char('Motivo', required=True, help='Por ejemplo: gripe, reposo médico, accidente.')
    certificado = fields.Binary('Certificado', attachment=True)
    certificado_nombre = fields.Char('Nombre del archivo')
    nota = fields.Text('Notas')

    @api.depends('desde', 'hasta')
    def _compute_dias(self):
        for reposo in self:
            reposo.dias = (reposo.hasta - reposo.desde).days + 1 if reposo.desde and reposo.hasta else 0

    @api.constrains('desde', 'hasta')
    def _check_fechas(self):
        for reposo in self:
            if reposo.hasta < reposo.desde:
                raise ValidationError('La fecha "hasta" no puede ser anterior a la fecha "desde".')

    @api.model_create_multi
    def create(self, vals_list):
        reposos = super().create(vals_list)
        reposos._actualizar_asistencias()
        return reposos

    def write(self, vals):
        anteriores = [(r.empleado_id, r.desde, r.hasta) for r in self]
        resultado = super().write(vals)
        self._actualizar_asistencias(anteriores)
        return resultado

    def unlink(self):
        anteriores = [(r.empleado_id, r.desde, r.hasta) for r in self]
        resultado = super().unlink()
        self.env['tienda.reposo']._actualizar_asistencias(anteriores)
        return resultado

    def _actualizar_asistencias(self, rangos=()):
        """Los días sin entrada dentro de un reposo quedan como "reposo"; si el reposo se
        borra o se acorta, vuelven a ser "falta"."""
        rangos = list(rangos) + [(r.empleado_id, r.desde, r.hasta) for r in self]
        for empleado, desde, hasta in rangos:
            dias = self.env['tienda.asistencia'].search([
                ('empleado_id', '=', empleado.id), ('fecha', '>=', desde), ('fecha', '<=', hasta),
                ('estado', 'in', ('falta', 'reposo')), ('pagado', '=', False)])
            for dia in dias:
                reposo = empleado._reposo_en(dia.fecha)
                estado = 'reposo' if reposo else 'falta'
                if dia.estado != estado:
                    dia.write({'estado': estado, 'nota': reposo.motivo if reposo else 'No marcó entrada'})
