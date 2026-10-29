# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

from .utiles import guaranies

ESTADOS_MANTENIMIENTO = [
    ('nuevo', 'Nuevo'),
    ('en_proceso', 'En proceso'),
    ('resuelto', 'Resuelto'),
    ('cancelado', 'Cancelado'),
]
QUIEN_PAGA = [
    ('dueno', 'El dueño'),
    ('inquilino', 'El inquilino'),
]


class AlquilerMantenimiento(models.Model):
    """Un pedido de reparación ("se rompió la canilla"). Al resolverlo, el costo va a los gastos de la propiedad
    y, si lo paga el inquilino, además se le suma a su próxima cuota."""
    _name = 'alquiler.mantenimiento'
    _description = 'Pedido de mantenimiento'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'prioridad desc, fecha desc, id desc'

    name = fields.Char('Qué pasó', required=True, tracking=True)
    unidad_id = fields.Many2one('alquiler.unidad', string='Unidad', required=True, tracking=True, index=True)
    propiedad_id = fields.Many2one(related='unidad_id.propiedad_id', store=True, string='Propiedad')
    inquilino_id = fields.Many2one('res.partner', string='Avisó', compute='_compute_inquilino_id', store=True,
                                   readonly=False, precompute=True)
    fecha = fields.Date('Fecha', required=True, default=fields.Date.context_today)
    prioridad = fields.Selection([('0', 'Normal'), ('1', 'Urgente')], string='Prioridad', default='0')
    estado = fields.Selection(ESTADOS_MANTENIMIENTO, string='Estado', default='nuevo', required=True,
                              tracking=True, group_expand='_group_expand_estado')
    responsable = fields.Char('Quién lo arregla', tracking=True, help='El plomero, el electricista...')
    costo = fields.Monetary('Costo', tracking=True)
    paga = fields.Selection(QUIEN_PAGA, string='Paga', required=True, default='dueno', tracking=True)
    fecha_resuelto = fields.Date('Resuelto el', readonly=True, copy=False)
    gasto_id = fields.Many2one('alquiler.gasto', string='Gasto', readonly=True, copy=False)
    cargo_id = fields.Many2one('alquiler.cuota.cargo', string='Cargo al inquilino', readonly=True, copy=False)
    foto = fields.Image('Foto', max_width=1280, max_height=1280)
    nota = fields.Text('Notas')
    company_id = fields.Many2one(related='unidad_id.company_id', store=True)
    currency_id = fields.Many2one(related='company_id.currency_id')

    @api.model
    def _group_expand_estado(self, estados, domain):
        return [clave for clave, _etiqueta in ESTADOS_MANTENIMIENTO]

    @api.depends('unidad_id')
    def _compute_inquilino_id(self):
        for pedido in self:
            pedido.inquilino_id = pedido.unidad_id.inquilino_id

    def action_en_proceso(self):
        self.write({'estado': 'en_proceso'})
        return True

    def action_cancelar(self):
        self.write({'estado': 'cancelado'})
        return True

    def action_resolver(self):
        """Lo da por resuelto. Si tiene costo, lo carga como gasto de la propiedad y, si lo paga el inquilino,
        además se lo suma a su cuota."""
        hoy = fields.Date.context_today(self)
        for pedido in self:
            if pedido.estado in ('resuelto', 'cancelado'):
                raise UserError(f'El pedido "{pedido.name}" ya está {dict(ESTADOS_MANTENIMIENTO)[pedido.estado].lower()}.')
            valores = {'estado': 'resuelto', 'fecha_resuelto': hoy}
            if pedido.costo > 0 and pedido.paga == 'inquilino':
                contrato = pedido.unidad_id.contrato_id
                cuota = contrato._cuota_para_cargos() if contrato else None
                if not cuota:
                    raise UserError(f'{pedido.unidad_id.display_name} no tiene un contrato vigente con cuotas para '
                                    'cobrarle la reparación. Elija que paga el dueño.')
                valores['cargo_id'] = self.env['alquiler.cuota.cargo'].create({
                    'cuota_id': cuota.id,
                    'concepto': 'reparacion',
                    'detalle': pedido.name,
                    'monto': pedido.costo,
                    'mantenimiento_id': pedido.id,
                }).id
                contrato.message_post(body=f'Se suma a la cuota de {cuota.name} la reparación "{pedido.name}": '
                                           f'{guaranies(pedido.costo)}.')
            if pedido.costo > 0:
                # Al que lo arregla le paga el dueño, aunque después se lo cobre al inquilino: el gasto va siempre, así
                # la ganancia cuadra (lo que paga el inquilino entra como cobrado con su cuota).
                # Con sudo: el encargado de cobros carga y resuelve reparaciones, pero solo puede leer los gastos.
                # La empresa del gasto sale de la propiedad, igual que la del pedido.
                cobrado = ' (se le cobra al inquilino)' if pedido.paga == 'inquilino' else ''
                valores['gasto_id'] = self.env['alquiler.gasto'].sudo().create({
                    'name': f'{pedido.name}{cobrado}',
                    'fecha': hoy,
                    'propiedad_id': pedido.propiedad_id.id,
                    'unidad_id': pedido.unidad_id.id,
                    'categoria': 'reparacion',
                    'monto': pedido.costo,
                    'proveedor': pedido.responsable,
                    'mantenimiento_id': pedido.id,
                }).id
            pedido.write(valores)
        return True
