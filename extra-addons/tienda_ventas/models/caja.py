# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .venta import METODOS_PAGO


class TiendaCaja(models.Model):
    """Turno de caja de un cajero: se abre con un fondo inicial, cada venta confirmada
    queda registrada en la caja abierta y al cerrar se cuenta el efectivo."""
    _name = 'tienda.caja'
    _description = 'Caja'
    _order = 'fecha_apertura desc, id desc'

    name = fields.Char('Número', readonly=True, copy=False, default='Nueva')
    usuario_id = fields.Many2one('res.users', string='Cajero', required=True, readonly=True, index=True,
                                 default=lambda self: self.env.user)
    estado = fields.Selection([
        ('abierta', 'Abierta'),
        ('cerrada', 'Cerrada'),
    ], string='Estado', default='abierta', required=True, readonly=True, copy=False)
    fecha_apertura = fields.Datetime('Apertura', default=fields.Datetime.now, required=True, readonly=True)
    fecha_cierre = fields.Datetime('Cierre', readonly=True, copy=False)
    currency_id = fields.Many2one(
        'res.currency', string='Moneda', required=True,
        default=lambda self: self.env.company.currency_id)
    monto_inicial = fields.Monetary('Fondo inicial',
                                    help='Efectivo que hay en la caja al abrirla, para dar vuelto.')
    venta_ids = fields.One2many('tienda.venta', 'caja_id', string='Ventas')
    nota = fields.Text('Notas')

    cantidad_ventas = fields.Integer('Ventas confirmadas', compute='_compute_totales', store=True)
    total_efectivo = fields.Monetary('Efectivo', compute='_compute_totales', store=True)
    total_tarjeta = fields.Monetary('Tarjeta', compute='_compute_totales', store=True)
    total_transferencia = fields.Monetary('Transferencia / QR', compute='_compute_totales', store=True)
    total_ventas = fields.Monetary('Total vendido', compute='_compute_totales', store=True)
    iva_10 = fields.Monetary('IVA 10 %', compute='_compute_totales', store=True)
    iva_5 = fields.Monetary('IVA 5 %', compute='_compute_totales', store=True)

    efectivo_esperado = fields.Monetary('Efectivo esperado', compute='_compute_efectivo', store=True,
                                        help='Fondo inicial + ventas en efectivo.')
    efectivo_contado = fields.Monetary('Efectivo contado', readonly=True, copy=False)
    diferencia = fields.Monetary('Diferencia', compute='_compute_efectivo', store=True,
                                 help='Positiva si sobra efectivo, negativa si falta.')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nueva') == 'Nueva':
                vals['name'] = self.env['ir.sequence'].next_by_code('tienda.caja') or 'Nueva'
        return super().create(vals_list)

    @api.constrains('estado', 'usuario_id')
    def _check_una_caja_abierta_por_usuario(self):
        for caja in self.filtered(lambda c: c.estado == 'abierta'):
            abiertas = self.search_count([('usuario_id', '=', caja.usuario_id.id), ('estado', '=', 'abierta')])
            if abiertas > 1:
                raise ValidationError(f'{caja.usuario_id.name} ya tiene una caja abierta. '
                                      'Ciérrela antes de abrir otra.')

    @api.depends('venta_ids.estado', 'venta_ids.metodo_pago', 'venta_ids.total',
                 'venta_ids.iva_10', 'venta_ids.iva_5')
    def _compute_totales(self):
        for caja in self:
            ventas = caja.venta_ids.filtered(lambda v: v.estado == 'confirmada')
            por_metodo = {metodo: 0 for metodo, _nombre in METODOS_PAGO}
            for venta in ventas:
                por_metodo[venta.metodo_pago] += venta.total
            caja.cantidad_ventas = len(ventas)
            caja.total_efectivo = por_metodo['efectivo']
            caja.total_tarjeta = por_metodo['tarjeta']
            caja.total_transferencia = por_metodo['transferencia']
            caja.total_ventas = sum(por_metodo.values())
            caja.iva_10 = sum(ventas.mapped('iva_10'))
            caja.iva_5 = sum(ventas.mapped('iva_5'))

    @api.depends('monto_inicial', 'total_efectivo', 'efectivo_contado', 'estado')
    def _compute_efectivo(self):
        for caja in self:
            caja.efectivo_esperado = caja.monto_inicial + caja.total_efectivo
            caja.diferencia = caja.efectivo_contado - caja.efectivo_esperado if caja.estado == 'cerrada' else 0

    @api.model
    def _caja_abierta(self):
        """Caja abierta del usuario actual (vacío si no tiene)."""
        return self.search([('usuario_id', '=', self.env.uid), ('estado', '=', 'abierta')], limit=1)

    def action_cerrar(self):
        """Abre el asistente para contar el efectivo y cerrar la caja."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Cerrar caja',
            'res_model': 'tienda.caja.cierre.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_caja_id': self.id},
        }

    def _cerrar(self, efectivo_contado, nota=False):
        self.ensure_one()
        if self.estado != 'abierta':
            raise UserError(f'La caja {self.name} ya está cerrada.')
        self.write({
            'estado': 'cerrada',
            'fecha_cierre': fields.Datetime.now(),
            'efectivo_contado': efectivo_contado,
            'nota': '\n'.join(filter(None, [self.nota, nota])) or False,
        })

    def _alto_ticket_mm(self):
        """Largo del resumen impreso: siempre tiene los mismos renglones, más las notas."""
        self.ensure_one()
        alto = 140 + (12 if self.estado == 'abierta' else 0)
        if self.nota:
            alto += 10 + sum(4.5 * (1 + len(renglon) // 40) for renglon in self.nota.splitlines())
        return alto

    @api.ondelete(at_uninstall=False)
    def _unlink_solo_sin_ventas(self):
        for caja in self:
            if caja.estado == 'cerrada' or caja.venta_ids:
                raise UserError(f'No se puede eliminar la caja {caja.name}: ya tiene ventas o está cerrada.')
