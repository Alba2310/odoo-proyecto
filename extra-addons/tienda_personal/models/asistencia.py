# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .comun import hoy

ESTADOS = [
    ('presente', 'Presente'),
    ('falta', 'Falta sin aviso'),
    ('reposo', 'Reposo'),
    ('permiso', 'Permiso / feriado'),
]

# Campos que se pueden seguir cambiando en un día ya pagado.
EDITABLES_PAGADO = {'nota', 'pago_id'}


class TiendaAsistencia(models.Model):
    """Un registro por empleado y por día: si vino (con entrada y salida) o por qué no vino."""
    _name = 'tienda.asistencia'
    _description = 'Asistencia'
    _order = 'fecha desc, empleado_id'

    empleado_id = fields.Many2one('tienda.empleado', string='Empleado', required=True,
                                  ondelete='cascade', index=True)
    sucursal_id = fields.Many2one(related='empleado_id.sucursal_id', store=True, string='Sucursal')
    fecha = fields.Date('Fecha', required=True, default=lambda self: hoy(), index=True)
    estado = fields.Selection(ESTADOS, string='Estado', required=True, default='presente')
    entrada = fields.Datetime('Entrada')
    salida = fields.Datetime('Salida')
    horas = fields.Float('Horas', compute='_compute_horas', store=True)
    currency_id = fields.Many2one(related='empleado_id.currency_id')
    # Se copia del empleado: si después le cambia el pago por hora, los días ya cargados no cambian.
    pago_hora = fields.Monetary('Pago por hora', compute='_compute_pago_hora', store=True,
                                readonly=False, precompute=True)
    monto = fields.Monetary('A cobrar', compute='_compute_monto', store=True)
    automatica = fields.Boolean('Marcada por el sistema', readonly=True,
                                help='Falta o reposo que el sistema marcó porque no hubo entrada ese día.')
    pago_id = fields.Many2one('tienda.pago', string='Pago', readonly=True, ondelete='set null', index=True)
    pagado = fields.Boolean('Pagado', compute='_compute_pagado', store=True)
    nota = fields.Char('Nota')

    _sql_constraints = [
        ('un_registro_por_dia', 'unique(empleado_id, fecha)',
         'Ese empleado ya tiene un registro de asistencia en esa fecha.'),
    ]

    @api.depends('empleado_id', 'fecha')
    def _compute_display_name(self):
        for asistencia in self:
            fecha = asistencia.fecha.strftime('%d/%m/%Y') if asistencia.fecha else ''
            asistencia.display_name = f'{asistencia.empleado_id.name} · {fecha}'

    @api.depends('estado', 'entrada', 'salida')
    def _compute_horas(self):
        for asistencia in self:
            trabajo = asistencia.estado == 'presente' and asistencia.entrada and asistencia.salida
            asistencia.horas = (asistencia.salida - asistencia.entrada).total_seconds() / 3600 if trabajo else 0

    @api.depends('empleado_id')
    def _compute_pago_hora(self):
        for asistencia in self:
            asistencia.pago_hora = asistencia.empleado_id.pago_hora

    @api.depends('horas', 'pago_hora', 'currency_id')
    def _compute_monto(self):
        # Pago por hora trabajada. Las faltas, reposos y permisos no se pagan.
        for asistencia in self:
            monto = asistencia.horas * asistencia.pago_hora
            asistencia.monto = asistencia.currency_id.round(monto) if asistencia.currency_id else monto

    @api.depends('pago_id.estado')
    def _compute_pagado(self):
        for asistencia in self:
            asistencia.pagado = asistencia.pago_id.estado == 'pagado'

    @api.constrains('estado', 'entrada', 'salida')
    def _check_horarios(self):
        for asistencia in self:
            if asistencia.estado == 'presente' and not asistencia.entrada:
                raise ValidationError('Para marcar a alguien como presente hay que cargar la hora de entrada.')
            if asistencia.entrada and asistencia.salida and asistencia.salida < asistencia.entrada:
                raise ValidationError('La hora de salida tiene que ser posterior a la de entrada.')

    def write(self, vals):
        if set(vals) - EDITABLES_PAGADO and any(self.mapped('pagado')):
            raise UserError('No se puede modificar un día que ya se pagó. Anule el pago primero.')
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_excepto_pagados(self):
        if any(self.mapped('pagado')):
            raise UserError('No se puede eliminar un día que ya se pagó. Anule el pago primero.')

    @api.model
    def _marcar_faltas(self, hasta=None):
        """Marca falta (o reposo, si tiene uno cargado) en cada día laboral sin registro.
        Revisa hasta ayer: el día de hoy todavía puede marcar la entrada. Lo ejecuta una
        tarea programada cada hora; se puede ejecutar varias veces sin duplicar nada."""
        hasta = hasta or hoy() - timedelta(days=1)
        limite = hasta - timedelta(days=31)
        nuevos = []
        for empleado in self.env['tienda.empleado'].search([]):
            desde = max(empleado.control_desde, limite)
            if desde > hasta:
                continue
            con_registro = set(self.search([('empleado_id', '=', empleado.id),
                                            ('fecha', '>=', desde), ('fecha', '<=', hasta)]).mapped('fecha'))
            dia = desde
            while dia <= hasta:
                if empleado._trabaja_el(dia) and dia not in con_registro:
                    reposo = empleado._reposo_en(dia)
                    nuevos.append({
                        'empleado_id': empleado.id,
                        'fecha': dia,
                        'estado': 'reposo' if reposo else 'falta',
                        'automatica': True,
                        'nota': reposo.motivo if reposo else 'No marcó entrada',
                    })
                dia += timedelta(days=1)
        return self.create(nuevos)
