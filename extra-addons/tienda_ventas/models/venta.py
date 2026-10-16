# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.tienda_inventario.models.producto import TIPOS_IVA

METODOS_PAGO = [
    ('efectivo', 'Efectivo'),
    ('tarjeta', 'Tarjeta'),
    ('transferencia', 'Transferencia / QR'),
]

# El precio ya incluye el IVA: IVA = precio / 11 (10 %) o precio / 21 (5 %).
DIVISOR_IVA = {'10': 11, '5': 21}


class TiendaVenta(models.Model):
    _name = 'tienda.venta'
    _description = 'Venta'
    _order = 'fecha desc, id desc'

    name = fields.Char('Número', readonly=True, copy=False, default='Nuevo')
    sucursal_id = fields.Many2one('tienda.sucursal', string='Sucursal', required=True, index=True,
                                  default=lambda self: self._default_sucursal())
    fecha = fields.Datetime('Fecha', default=fields.Datetime.now, required=True)
    cliente_id = fields.Many2one('res.partner', string='Cliente')
    vendedor_id = fields.Many2one('res.users', string='Vendedor', default=lambda self: self.env.user)
    estado = fields.Selection([
        ('borrador', 'Borrador'),
        ('confirmada', 'Confirmada'),
        ('cancelada', 'Cancelada'),
    ], string='Estado', default='borrador', required=True, readonly=True, copy=False)
    linea_ids = fields.One2many('tienda.venta.linea', 'venta_id', string='Productos', copy=True)
    movimiento_ids = fields.One2many('tienda.movimiento', 'venta_id', string='Movimientos de stock')
    nota = fields.Text('Notas')

    metodo_pago = fields.Selection(METODOS_PAGO, string='Forma de pago', default='efectivo', required=True)
    monto_recibido = fields.Monetary('Efectivo recibido',
                                     help='Con cuánto pagó el cliente. Se usa para calcular el vuelto.')
    vuelto = fields.Monetary('Vuelto', compute='_compute_vuelto')
    caja_id = fields.Many2one('tienda.caja', string='Caja', readonly=True, copy=False, index=True)
    caja_abierta_id = fields.Many2one('tienda.caja', string='Caja abierta del usuario',
                                      compute='_compute_caja_abierta_id')

    currency_id = fields.Many2one(
        'res.currency', string='Moneda', required=True,
        default=lambda self: self.env.company.currency_id)
    subtotal = fields.Monetary('Subtotal', compute='_compute_totales', store=True)
    descuento_total = fields.Monetary('Descuento', compute='_compute_totales', store=True)
    total = fields.Monetary('Total', compute='_compute_totales', store=True)
    iva_10 = fields.Monetary('IVA 10 %', compute='_compute_totales', store=True)
    iva_5 = fields.Monetary('IVA 5 %', compute='_compute_totales', store=True)

    @api.model
    def _default_sucursal(self):
        # La de la caja abierta del usuario; si no tiene, la sucursal donde trabaja.
        return self.env['tienda.caja']._caja_abierta().sucursal_id or self.env.user.tienda_sucursal_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code('tienda.venta') or 'Nuevo'
        return super().create(vals_list)

    @api.depends('linea_ids.subtotal', 'linea_ids.importe_descuento', 'linea_ids.importe_iva', 'linea_ids.iva')
    def _compute_totales(self):
        for venta in self:
            lineas = venta.linea_ids
            venta.total = sum(lineas.mapped('subtotal'))
            venta.descuento_total = sum(lineas.mapped('importe_descuento'))
            venta.subtotal = venta.total + venta.descuento_total
            venta.iva_10 = sum(lineas.filtered(lambda l: l.iva == '10').mapped('importe_iva'))
            venta.iva_5 = sum(lineas.filtered(lambda l: l.iva == '5').mapped('importe_iva'))

    @api.depends('metodo_pago', 'monto_recibido', 'total')
    def _compute_vuelto(self):
        for venta in self:
            pago_en_efectivo = venta.metodo_pago == 'efectivo' and venta.monto_recibido
            venta.vuelto = max(venta.monto_recibido - venta.total, 0) if pago_en_efectivo else 0

    def _compute_caja_abierta_id(self):
        self.caja_abierta_id = self.env['tienda.caja']._caja_abierta()

    def action_confirmar(self):
        """Confirma la venta, descuenta del stock lo vendido y la registra en la caja abierta."""
        caja = self.env['tienda.caja']._caja_abierta()
        if not caja:
            raise UserError('No tiene una caja abierta. Abra la caja en Ventas › Caja antes de confirmar ventas.')
        for venta in self:
            if venta.estado != 'borrador':
                raise UserError(f'La venta {venta.name} no está en borrador.')
            if not venta.linea_ids:
                raise UserError('Agregue al menos un producto antes de confirmar la venta.')
            if venta.sucursal_id != caja.sucursal_id:
                raise UserError(f'Su caja abierta ({caja.name}) es de {caja.sucursal_id.name} y la venta '
                                f'es de {venta.sucursal_id.name}. Cambie la sucursal de la venta.')
            otros = venta.linea_ids.producto_id.filtered(lambda p: p.sucursal_id != venta.sucursal_id)
            if otros:
                raise UserError(f'Estos productos no son de {venta.sucursal_id.name}: '
                                + ', '.join(otros.mapped('display_name')))
            if venta.metodo_pago == 'efectivo' and venta.monto_recibido and venta.monto_recibido < venta.total:
                raise UserError('El efectivo recibido es menor que el total de la venta.')
            venta._verificar_stock()
            # Se vende de la despensa de la sucursal.
            self.env['tienda.movimiento'].create([{
                'producto_id': linea.producto_id.id,
                'ubicacion': 'despensa',
                'tipo': 'venta',
                'cantidad': -linea.cantidad,
                'referencia': venta.name,
                'venta_id': venta.id,
            } for linea in venta.linea_ids])
            venta.write({'estado': 'confirmada', 'caja_id': caja.id})
        return True

    def _verificar_stock(self):
        self.ensure_one()
        pedido = defaultdict(float)
        for linea in self.linea_ids:
            pedido[linea.producto_id] += linea.cantidad
        faltantes = []
        for producto, cantidad in pedido.items():
            if cantidad > producto.stock_despensa:
                faltante = f'• {producto.display_name}: se quieren vender {cantidad:g} y en la despensa hay {producto.stock_despensa:g}'
                if producto.stock_deposito:
                    faltante += f' (en el depósito hay {producto.stock_deposito:g}: páselo a la despensa)'
                faltantes.append(faltante)
        if faltantes:
            raise UserError('No hay stock suficiente para confirmar la venta:\n' + '\n'.join(faltantes))

    def action_cancelar(self):
        """Cancela la venta. Si estaba confirmada, devuelve los productos al stock."""
        for venta in self:
            if venta.estado == 'cancelada':
                continue
            if venta.caja_id.estado == 'cerrada':
                raise UserError(f'No se puede cancelar la venta {venta.name}: '
                                f'la caja {venta.caja_id.name} ya se cerró.')
            if venta.estado == 'confirmada':
                # Se revierte el neto de la venta por producto, así una venta que
                # se canceló, volvió a borrador y se reconfirmó no se devuelve dos veces.
                neto = defaultdict(float)
                for movimiento in venta.movimiento_ids:
                    neto[movimiento.producto_id] += movimiento.cantidad
                self.env['tienda.movimiento'].create([{
                    'producto_id': producto.id,
                    'ubicacion': 'despensa',
                    'tipo': 'anulacion',
                    'cantidad': -cantidad,
                    'referencia': f'Anulación {venta.name}',
                    'venta_id': venta.id,
                } for producto, cantidad in neto.items() if cantidad])
            venta.estado = 'cancelada'
        return True

    def action_borrador(self):
        for venta in self:
            if venta.estado != 'cancelada':
                raise UserError('Solo una venta cancelada puede volver a borrador.')
            # Al reconfirmarla se registra en la caja que esté abierta en ese momento.
            venta.write({'estado': 'borrador', 'caja_id': False})
        return True

    def _alto_ticket_mm(self):
        """Largo aproximado del ticket impreso, para no gastar rollo en blanco.
        Cada producto ocupa dos renglones (~9 mm); los nombres largos, uno más."""
        self.ensure_one()
        alto = 120 + (10 if self.estado != 'confirmada' else 0)
        if self.metodo_pago == 'efectivo' and self.monto_recibido:
            alto += 9
        for linea in self.linea_ids:
            alto += 9 + 4.5 * (len(linea.producto_id.name or '') // 32)
        return alto

    @api.ondelete(at_uninstall=False)
    def _unlink_excepto_confirmadas(self):
        if any(venta.estado == 'confirmada' for venta in self):
            raise UserError('No se puede eliminar una venta confirmada. Cancélela primero.')


class TiendaVentaLinea(models.Model):
    _name = 'tienda.venta.linea'
    _description = 'Línea de venta'

    venta_id = fields.Many2one('tienda.venta', string='Venta', required=True,
                               ondelete='cascade', index=True)
    producto_id = fields.Many2one('tienda.producto', string='Producto', required=True, ondelete='restrict')
    stock_disponible = fields.Float(related='producto_id.stock_despensa', string='En despensa')
    cantidad = fields.Float('Cantidad', default=1, required=True)
    currency_id = fields.Many2one(related='venta_id.currency_id')
    precio_unitario = fields.Monetary('Precio unitario', compute='_compute_precio_unitario',
                                      store=True, readonly=False, precompute=True)
    descuento = fields.Float('Desc. (%)', default=0)
    # Se copia del producto al vender: si después cambia el IVA del producto, la venta no cambia.
    iva = fields.Selection(TIPOS_IVA, string='IVA', compute='_compute_iva', store=True, precompute=True)
    importe_descuento = fields.Monetary('Importe descuento', compute='_compute_importes', store=True)
    subtotal = fields.Monetary('Subtotal', compute='_compute_importes', store=True)
    importe_iva = fields.Monetary('IVA incluido', compute='_compute_importes', store=True)

    # Para el reporte de productos vendidos.
    sucursal_id = fields.Many2one(related='venta_id.sucursal_id', store=True, string='Sucursal')
    fecha = fields.Datetime(related='venta_id.fecha', store=True, string='Fecha')
    estado = fields.Selection(related='venta_id.estado', store=True, string='Estado')

    _sql_constraints = [
        ('cantidad_positiva', 'CHECK(cantidad > 0)', 'La cantidad vendida debe ser mayor que cero.'),
        ('descuento_valido', 'CHECK(descuento >= 0 AND descuento <= 100)',
         'El descuento debe estar entre 0 y 100 %.'),
    ]

    @api.depends('producto_id')
    def _compute_precio_unitario(self):
        for linea in self:
            linea.precio_unitario = linea.producto_id.precio_venta

    @api.depends('producto_id')
    def _compute_iva(self):
        for linea in self:
            linea.iva = linea.producto_id.iva

    @api.depends('cantidad', 'precio_unitario', 'descuento', 'iva', 'currency_id')
    def _compute_importes(self):
        for linea in self:
            redondear = linea.currency_id.round if linea.currency_id else (lambda importe: importe)
            bruto = linea.cantidad * linea.precio_unitario
            linea.importe_descuento = redondear(bruto * linea.descuento / 100)
            linea.subtotal = redondear(bruto - linea.importe_descuento)
            divisor = DIVISOR_IVA.get(linea.iva)
            linea.importe_iva = redondear(linea.subtotal / divisor) if divisor else 0
