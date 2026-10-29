# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import format_amount

ESTADOS_LIQUIDACION = [
    ('borrador', 'Borrador'),
    ('pagada', 'Pagada'),
]
# Lo que se puede seguir cambiando con la liquidación pagada.
CAMPOS_LIQUIDACION_PAGADA = {'estado', 'nota', 'fecha_pago'}


class BellaLiquidacionComision(models.Model):
    """Comisiones de una estilista en un período: un porcentaje de los servicios que hizo y de los productos que
    vendió en sus citas cobradas en el período (precios con IVA incluido, como se cobraron).

    Cuenta el día del cobro (la fecha de la factura, como en el cierre de caja), no el del turno: una cita que se
    cobra después de pagar la liquidación de su día entra en la del período en que se cobró. Las citas cuya factura
    se anuló entera con notas de crédito no cuentan.

    Cada servicio y cada producto entra en una sola liquidación (``liquidacion_id`` en la línea de la cita), así
    nada se paga dos veces. Los porcentajes salen de la ficha de la estilista y se pueden ajustar en el borrador.
    """
    _name = 'bella.liquidacion.comision'
    _description = 'Liquidación de comisiones'
    _inherit = ['mail.thread']
    _order = 'fecha_hasta desc, id desc'
    _check_company_auto = True

    name = fields.Char('Nombre', compute='_compute_name', store=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                 default=lambda self: self.env.company)
    estilista_id = fields.Many2one('hr.employee', string='Estilista', required=True, tracking=True, index=True,
                                   check_company=True, domain=[('bella_estilista', '=', True)])
    fecha_desde = fields.Date('Desde', required=True, tracking=True,
                              default=lambda self: fields.Date.context_today(self).replace(day=1))
    fecha_hasta = fields.Date('Hasta', required=True, tracking=True, default=fields.Date.context_today)
    estado = fields.Selection(ESTADOS_LIQUIDACION, string='Estado', default='borrador', required=True,
                              readonly=True, tracking=True, copy=False)
    servicio_ids = fields.One2many('bella.cita.servicio', 'liquidacion_id', string='Servicios', readonly=True)
    producto_ids = fields.One2many('bella.cita.producto', 'liquidacion_id', string='Productos', readonly=True)
    currency_id = fields.Many2one(related='company_id.currency_id')

    porcentaje_servicios = fields.Float('% por servicios', compute='_compute_porcentajes', store=True,
                                        readonly=False, precompute=True, tracking=True)
    porcentaje_productos = fields.Float('% por productos', compute='_compute_porcentajes', store=True,
                                        readonly=False, precompute=True, tracking=True)
    base_servicios = fields.Monetary('Servicios realizados', compute='_compute_comisiones', store=True)
    base_productos = fields.Monetary('Productos vendidos', compute='_compute_comisiones', store=True)
    comision_servicios = fields.Monetary('Comisión por servicios', compute='_compute_comisiones', store=True)
    comision_productos = fields.Monetary('Comisión por productos', compute='_compute_comisiones', store=True)
    adelantos = fields.Monetary('Adelantos', tracking=True,
                                help='Lo que ya se le entregó a cuenta en el período (vales, adelantos).')
    total = fields.Monetary('A pagar', compute='_compute_comisiones', store=True, tracking=True)
    fecha_pago = fields.Date('Pagada el', readonly=True, copy=False)
    nota = fields.Text('Notas')

    @api.depends('estilista_id', 'fecha_desde', 'fecha_hasta')
    def _compute_name(self):
        for liquidacion in self:
            periodo = ''
            if liquidacion.fecha_desde and liquidacion.fecha_hasta:
                periodo = (f'{liquidacion.fecha_desde.strftime("%d/%m")} al '
                           f'{liquidacion.fecha_hasta.strftime("%d/%m/%Y")}')
            partes = (liquidacion.estilista_id.name, periodo)
            liquidacion.name = ' · '.join(parte for parte in partes if parte) or 'Liquidación de comisiones'

    @api.depends('estilista_id')
    def _compute_porcentajes(self):
        for liquidacion in self:
            estilista = liquidacion.estilista_id.sudo()
            liquidacion.porcentaje_servicios = estilista.bella_comision_servicios
            liquidacion.porcentaje_productos = estilista.bella_comision_productos

    @api.depends('servicio_ids.precio', 'producto_ids.subtotal', 'porcentaje_servicios', 'porcentaje_productos',
                 'adelantos', 'currency_id')
    def _compute_comisiones(self):
        for liquidacion in self:
            redondear = liquidacion.currency_id.round if liquidacion.currency_id else round
            liquidacion.base_servicios = sum(liquidacion.servicio_ids.mapped('precio'))
            liquidacion.base_productos = sum(liquidacion.producto_ids.mapped('subtotal'))
            liquidacion.comision_servicios = redondear(
                liquidacion.base_servicios * liquidacion.porcentaje_servicios / 100)
            liquidacion.comision_productos = redondear(
                liquidacion.base_productos * liquidacion.porcentaje_productos / 100)
            liquidacion.total = (liquidacion.comision_servicios + liquidacion.comision_productos
                                 - liquidacion.adelantos)

    @api.constrains('fecha_desde', 'fecha_hasta')
    def _check_fechas(self):
        for liquidacion in self:
            if liquidacion.fecha_hasta < liquidacion.fecha_desde:
                raise ValidationError('La fecha "Hasta" no puede ser anterior a "Desde".')

    @api.model_create_multi
    def create(self, vals_list):
        liquidaciones = super().create(vals_list)
        liquidaciones._buscar_lineas()
        return liquidaciones

    def write(self, vals):
        if set(vals) - CAMPOS_LIQUIDACION_PAGADA and any(liq.estado == 'pagada' for liq in self):
            raise UserError('La liquidación ya está pagada: para corregirla, primero hay que volverla a borrador.')
        resultado = super().write(vals)
        if {'estilista_id', 'fecha_desde', 'fecha_hasta'} & set(vals):
            self._buscar_lineas()
        return resultado

    @api.ondelete(at_uninstall=False)
    def _unlink_excepto_pagadas(self):
        if any(liquidacion.estado == 'pagada' for liquidacion in self):
            raise UserError('No se puede eliminar una liquidación pagada.')

    # Servicios y productos del período

    def _buscar_lineas(self):
        """Junta los servicios y productos de las citas cobradas en el período que todavía no se liquidaron."""
        for liquidacion in self.filtered(lambda liq: liq.estado == 'borrador'):
            dominio = [
                ('liquidacion_id', 'in', (False, liquidacion.id)),
                ('cita_id.estilista_id', '=', liquidacion.estilista_id.id),
                ('cita_id.factura_id.invoice_date', '>=', liquidacion.fecha_desde),
                ('cita_id.factura_id.invoice_date', '<=', liquidacion.fecha_hasta),
            ]
            servicios = self.env['bella.cita.servicio'].search(dominio)
            productos = self.env['bella.cita.producto'].search(dominio)
            anuladas = (servicios.cita_id | productos.cita_id).filtered(lambda cita: cita._bella_factura_anulada())
            servicios = servicios.filtered(lambda linea: linea.cita_id not in anuladas)
            productos = productos.filtered(lambda linea: linea.cita_id not in anuladas)
            (liquidacion.servicio_ids - servicios).liquidacion_id = False
            (liquidacion.producto_ids - productos).liquidacion_id = False
            servicios.liquidacion_id = liquidacion
            productos.liquidacion_id = liquidacion

    # Botones

    def action_actualizar(self):
        """Por si se cobraron citas del período después de crear la liquidación."""
        if any(liquidacion.estado != 'borrador' for liquidacion in self):
            raise UserError('Solo se actualiza una liquidación en borrador.')
        self._buscar_lineas()
        return True

    def action_pagar(self):
        for liquidacion in self:
            if liquidacion.estado != 'borrador':
                raise UserError(f'La liquidación {liquidacion.name} ya está pagada.')
            if not liquidacion.servicio_ids and not liquidacion.producto_ids:
                raise UserError(f'{liquidacion.estilista_id.name} no tiene servicios ni productos cobrados '
                                'en ese período.')
            if liquidacion.currency_id.compare_amounts(liquidacion.total, 0) < 0:
                raise UserError('Los adelantos son más que las comisiones: revise el monto de los adelantos.')
            liquidacion.write({'estado': 'pagada', 'fecha_pago': fields.Date.context_today(liquidacion)})
            liquidacion.message_post(body=Markup('Comisiones pagadas: <b>%s</b>.') % format_amount(
                self.env, liquidacion.total, liquidacion.currency_id))
        return True

    def action_borrador(self):
        self.write({'estado': 'borrador', 'fecha_pago': False})
        return True
