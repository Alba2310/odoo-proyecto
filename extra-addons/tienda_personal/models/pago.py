# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

from .comun import hoy


class TiendaPago(models.Model):
    """Pago a un empleado: junta los días trabajados, bonos y sanciones que tenía pendientes.
    Cada día, bono o sanción queda en un solo pago, así nada se paga dos veces."""
    _name = 'tienda.pago'
    _description = 'Pago al empleado'
    _order = 'fecha desc, id desc'

    name = fields.Char('Número', readonly=True, copy=False, default='Nuevo')
    empleado_id = fields.Many2one('tienda.empleado', string='Empleado', required=True, index=True,
                                  ondelete='restrict')
    sucursal_id = fields.Many2one(related='empleado_id.sucursal_id', store=True, string='Sucursal')
    fecha = fields.Date('Fecha de pago', default=lambda self: hoy(), required=True)
    estado = fields.Selection([
        ('borrador', 'Por pagar'),
        ('pagado', 'Pagado'),
        ('anulado', 'Anulado'),
    ], string='Estado', default='borrador', required=True, readonly=True, copy=False)
    asistencia_ids = fields.One2many('tienda.asistencia', 'pago_id', string='Días trabajados')
    ajuste_ids = fields.One2many('tienda.ajuste', 'pago_id', string='Bonos y sanciones')
    nota = fields.Text('Notas')

    currency_id = fields.Many2one(related='empleado_id.currency_id')
    desde = fields.Date('Desde', compute='_compute_totales', store=True)
    hasta = fields.Date('Hasta', compute='_compute_totales', store=True)
    dias = fields.Integer('Cant. de días', compute='_compute_totales', store=True)
    horas = fields.Float('Horas', compute='_compute_totales', store=True)
    monto_horas = fields.Monetary('Por horas trabajadas', compute='_compute_totales', store=True)
    total_bonos = fields.Monetary('Bonos', compute='_compute_totales', store=True)
    total_sanciones = fields.Monetary('Sanciones', compute='_compute_totales', store=True)
    total = fields.Monetary('Total a pagar', compute='_compute_totales', store=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code('tienda.pago') or 'Nuevo'
        return super().create(vals_list)

    @api.depends('asistencia_ids.fecha', 'asistencia_ids.horas', 'asistencia_ids.monto',
                 'ajuste_ids.tipo', 'ajuste_ids.monto')
    def _compute_totales(self):
        for pago in self:
            dias = pago.asistencia_ids
            fechas = dias.mapped('fecha') + pago.ajuste_ids.mapped('fecha')
            pago.desde = min(fechas) if fechas else False
            pago.hasta = max(fechas) if fechas else False
            pago.dias = len(dias)
            pago.horas = sum(dias.mapped('horas'))
            pago.monto_horas = sum(dias.mapped('monto'))
            pago.total_bonos = sum(pago.ajuste_ids.filtered(lambda a: a.tipo == 'bono').mapped('monto'))
            pago.total_sanciones = sum(pago.ajuste_ids.filtered(lambda a: a.tipo == 'sancion').mapped('monto'))
            pago.total = pago.monto_horas + pago.total_bonos - pago.total_sanciones

    def _cargar_pendientes(self):
        """Agrega al pago todo lo que el empleado tiene sin pagar hasta la fecha del pago.
        Los días sin hora de salida no se agregan: primero hay que corregirlos."""
        for pago in self.filtered(lambda p: p.estado == 'borrador'):
            pago.env['tienda.asistencia'].search([
                ('empleado_id', '=', pago.empleado_id.id), ('pago_id', '=', False),
                ('estado', '=', 'presente'), ('salida', '!=', False), ('fecha', '<=', pago.fecha),
            ]).pago_id = pago
            pago.env['tienda.ajuste'].search([
                ('empleado_id', '=', pago.empleado_id.id), ('pago_id', '=', False),
                ('fecha', '<=', pago.fecha),
            ]).pago_id = pago

    def action_actualizar(self):
        self._cargar_pendientes()
        return True

    def action_confirmar(self):
        """Marca el pago como hecho y descarga el recibo para que lo firme el empleado."""
        for pago in self:
            if pago.estado != 'borrador':
                raise UserError(f'El pago {pago.name} no está pendiente.')
            if not (pago.asistencia_ids or pago.ajuste_ids):
                raise UserError('El pago no tiene días trabajados, bonos ni sanciones.')
            if pago.total < 0:
                raise UserError('Las sanciones superan lo que se le debe al empleado: el total no puede ser negativo.')
            pago.estado = 'pagado'
        return self.env.ref('tienda_personal.action_report_recibo_pago').report_action(self, config=False)

    def action_anular(self):
        """Anula un pago hecho por error: sus días, bonos y sanciones vuelven a quedar pendientes."""
        for pago in self:
            if pago.estado != 'pagado':
                raise UserError('Solo se puede anular un pago ya hecho.')
            pago.estado = 'anulado'
            pago.asistencia_ids.pago_id = False
            pago.ajuste_ids.pago_id = False
        return True

    def _alto_ticket_mm(self):
        """Largo del recibo impreso: un renglón por día trabajado y por bono o sanción."""
        self.ensure_one()
        alto = 105 + 4.5 * len(self.asistencia_ids)
        if self.ajuste_ids:
            alto += 10 + 4.5 * len(self.ajuste_ids)
        return alto

    @api.ondelete(at_uninstall=False)
    def _unlink_solo_borrador(self):
        if any(pago.estado == 'pagado' for pago in self):
            raise UserError('No se puede eliminar un pago hecho. Anúlelo en su lugar.')
