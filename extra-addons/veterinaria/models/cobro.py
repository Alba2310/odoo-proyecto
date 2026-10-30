# -*- coding: utf-8 -*-
from collections import defaultdict

from markupsafe import Markup

from odoo import Command, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, format_amount

FORMAS_PAGO = [
    ('efectivo', 'Efectivo'),
    ('tarjeta', 'Tarjeta'),
    ('transferencia', 'Transferencia / QR'),
]


class VetCobrable(models.AbstractModel):
    """Lo que tienen en común la atención, la internación y la venta de mostrador al cobrarse: la factura, los
    pagos (pueden ser varios, uno por forma de pago) y la salida del stock.

    El modelo que lo hereda tiene ``name``, ``company_id``, ``currency_id``, ``total`` y el cliente en
    ``dueno_id``, hereda ``mail.thread`` y define ``_vet_lineas_factura`` y ``_vet_lineas_vendidas``.
    """
    _name = 'vet.cobrable'
    _description = 'Documento que se cobra con factura'

    factura_id = fields.Many2one('account.move', string='Factura', readonly=True, copy=False)
    factura_moneda_id = fields.Many2one(related='factura_id.currency_id', string='Moneda de la factura')
    monto_cobrado = fields.Monetary(related='factura_id.amount_total', string='Cobrado',
                                    currency_field='factura_moneda_id')
    estado_pago = fields.Selection(related='factura_id.payment_state', string='Estado de pago')
    forma_pago = fields.Char('Forma de pago', readonly=True, copy=False,
                             help='Cómo se pagó: puede ser una parte en efectivo y otra con tarjeta.')
    movimiento_ids = fields.Many2many('stock.move', string='Movimientos de stock', readonly=True, copy=False)
    movimiento_count = fields.Integer(compute='_compute_movimiento_count')

    def _compute_movimiento_count(self):
        for documento in self:
            documento.movimiento_count = len(documento.movimiento_ids)

    # Lo que define cada documento

    def _vet_lineas_factura(self):
        """Comandos ``Command.create`` con las líneas de la factura."""
        raise NotImplementedError()

    def _vet_lineas_vendidas(self):
        """Líneas (modelos que heredan ``vet.linea.venta``) con lo que sale del stock al cobrar."""
        raise NotImplementedError()

    def _vet_falta_stock_frena(self):
        """Si falta stock de un producto, ¿se puede cobrar igual? En la internación los remedios ya se usaron."""
        return True

    # Cobro

    def _vet_cobrar(self, pagos, fecha=None):
        """Emite la factura, registra un pago por cada forma de pago y saca del stock lo vendido.

        ``pagos``: ``{'efectivo': monto, 'tarjeta': monto, ...}``; tienen que sumar el total.
        """
        self.ensure_one()
        if self.factura_id:
            raise UserError(f'{self.name} ya está cobrado con la factura {self.factura_id.name}.')
        lineas = self._vet_lineas_factura()
        if not lineas:
            raise UserError('No hay nada para cobrar: cargue al menos un servicio o un producto.')
        moneda = self.currency_id
        if any(moneda.compare_amounts(monto, 0) < 0 for monto in pagos.values()):
            raise UserError('Los montos de cada forma de pago no pueden ser negativos.')
        pagos = {metodo: monto for metodo, monto in pagos.items() if not moneda.is_zero(monto)}
        if moneda.compare_amounts(sum(pagos.values()), self.total) != 0:
            raise UserError(f'Los pagos suman {format_amount(self.env, sum(pagos.values()), moneda)} y el total es '
                            f'{format_amount(self.env, self.total, moneda)}.')
        self._vet_verificar_stock()
        fecha = fecha or fields.Date.context_today(self)

        factura = self.env['account.move'].with_company(self.company_id).create({
            'move_type': 'out_invoice',
            'partner_id': self.dueno_id.id,
            'invoice_date': fecha,
            'invoice_origin': self.name,
            'invoice_user_id': self.env.user.id,
            'company_id': self.company_id.id,
            'invoice_line_ids': lineas,
        })
        factura.action_post()
        if moneda.compare_amounts(factura.amount_total, self.total) != 0:
            # Un producto con el IVA sin incluir en el precio cambia el total: mejor no cobrar distinto de lo que
            # se le dijo al dueño.
            raise UserError(f'El total de la factura ({format_amount(self.env, factura.amount_total, moneda)}) no '
                            f'coincide con el de {self.name} ({format_amount(self.env, self.total, moneda)}). Revise '
                            'que los impuestos de los productos tengan el IVA incluido en el precio.')
        for metodo, monto in pagos.items():
            self.env['account.payment.register'].with_context(
                active_model='account.move', active_ids=factura.ids,
            ).create({
                'journal_id': self._vet_diario(metodo).id,
                'payment_date': fecha,
                'amount': monto,
                'payment_difference_handling': 'open',
                'communication': f'{factura.name} · {dict(FORMAS_PAGO)[metodo]}',
            })._create_payments()

        texto = ' + '.join(f'{dict(FORMAS_PAGO)[metodo]} {format_amount(self.env, monto, moneda)}'
                           for metodo, monto in pagos.items()) or 'Sin cargo'
        self.write({'factura_id': factura.id, 'forma_pago': texto})
        self._vet_descontar_stock()
        self.message_post(body=Markup('Cobrado con la factura %s: %s.') % (factura._get_html_link(), texto))
        return factura

    def _vet_diario(self, metodo):
        """El diario que eligió la veterinaria en Ajustes o, si no eligió, el de caja (efectivo) o el de banco."""
        company = self.company_id
        diario = {
            'efectivo': company.vet_diario_efectivo_id,
            'tarjeta': company.vet_diario_tarjeta_id,
            'transferencia': company.vet_diario_transferencia_id,
        }[metodo]
        if not diario:
            diario = self.env['account.journal'].search([
                ('company_id', '=', company.id),
                ('type', '=', 'cash' if metodo == 'efectivo' else 'bank'),
            ], limit=1)
        if not diario:
            raise UserError(f'No hay un diario de {"caja" if metodo == "efectivo" else "banco"} en Facturación para '
                            f'registrar el pago con {dict(FORMAS_PAGO)[metodo].lower()}.')
        return diario

    # Stock

    def _vet_almacen(self):
        almacen = self.env['stock.warehouse'].search([('company_id', '=', self.company_id.id)], limit=1)
        if not almacen:
            raise UserError(f'{self.company_id.name} no tiene un depósito en Inventario.')
        return almacen

    def _vet_cantidades(self):
        """Lo vendido sumado por producto, solo de los productos con control de stock."""
        cantidades = defaultdict(float)
        for linea in self._vet_lineas_vendidas():
            if linea.producto_id.is_storable:
                cantidades[linea.producto_id] += linea.cantidad
        return cantidades

    def _vet_verificar_stock(self):
        if not self._vet_falta_stock_frena():
            return
        ubicacion = self._vet_almacen().lot_stock_id
        faltantes = []
        for producto, cantidad in self._vet_cantidades().items():
            disponible = producto.with_context(location=ubicacion.id).qty_available
            if float_compare(cantidad, disponible, precision_rounding=producto.uom_id.rounding) > 0:
                faltantes.append(f'• {producto.display_name}: se venden {cantidad:g} y hay {disponible:g}')
        if faltantes:
            raise UserError('No hay stock suficiente para cobrar:\n' + '\n'.join(faltantes)
                            + '\nCargue el stock en Inventario o quite el producto.')

    def _vet_descontar_stock(self):
        origen = self._vet_almacen().lot_stock_id
        clientes = self.env.ref('stock.stock_location_customers')
        cantidades = self._vet_cantidades()
        if not cantidades:
            return
        movimientos = self.env['stock.move'].create([{
            'name': f'{self.name}: {producto.display_name}',
            'origin': self.name,
            'product_id': producto.id,
            'product_uom': producto.uom_id.id,
            'product_uom_qty': cantidad,
            'location_id': origen.id,
            'location_dest_id': clientes.id,
            'partner_id': self.dueno_id.id,
            'company_id': self.company_id.id,
        } for producto, cantidad in cantidades.items()])._action_confirm()
        movimientos._action_assign()
        for movimiento in movimientos:
            movimiento.quantity = movimiento.product_uom_qty
        movimientos.picked = True
        movimientos._action_done()
        self.movimiento_ids = [Command.link(movimiento.id) for movimiento in movimientos]
        en_negativo = [producto.display_name for producto in cantidades
                       if producto.with_context(location=origen.id).qty_available < 0]
        if en_negativo:
            self.message_post(body='Quedó stock negativo de: ' + ', '.join(en_negativo) + '. Revise el inventario.')

    # Botones

    def action_ver_factura(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Factura',
            'res_model': 'account.move',
            'res_id': self.factura_id.id,
            'view_mode': 'form',
        }

    def action_ver_movimientos(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('stock.stock_move_action')
        action['domain'] = [('id', 'in', self.movimiento_ids.ids)]
        action['context'] = {'create': False}
        return action

    def _vet_abrir_cobro(self, campo):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Cobrar {self.name}',
            'res_model': 'vet.cobro.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {f'default_{campo}': self.id},
        }


class VetLineaVenta(models.AbstractModel):
    """Un servicio o producto que se cobra (en la atención, la internación o el mostrador). Cobrado el documento,
    la línea ya no cambia: su factura está emitida.

    Cada modelo concreto define el documento (``_vet_documento``) y redefine ``company_id`` y ``currency_id``
    como campos relacionados con él.
    """
    _name = 'vet.linea.venta'
    _description = 'Línea que se cobra'

    sequence = fields.Integer(default=10)
    company_id = fields.Many2one('res.company', string='Compañía')
    currency_id = fields.Many2one('res.currency', string='Moneda')
    producto_id = fields.Many2one('product.product', string='Servicio o producto', required=True,
                                  check_company=True, domain=[('sale_ok', '=', True)])
    cantidad = fields.Float('Cantidad', default=1, required=True, digits='Product Unit of Measure')
    uom_id = fields.Many2one(related='producto_id.uom_id', string='Unidad')
    es_almacenable = fields.Boolean(related='producto_id.is_storable')
    stock_disponible = fields.Float('En stock', compute='_compute_stock_disponible',
                                    digits='Product Unit of Measure')
    precio_unitario = fields.Monetary('Precio', compute='_compute_precio_unitario', store=True, readonly=False,
                                      precompute=True)
    subtotal = fields.Monetary('Subtotal', compute='_compute_subtotal', store=True)

    _sql_constraints = [
        ('cantidad_positiva', 'CHECK(cantidad > 0)', 'La cantidad tiene que ser mayor que cero.'),
    ]

    def _vet_documento(self):
        raise NotImplementedError()

    @api.depends('producto_id', 'company_id')
    def _compute_stock_disponible(self):
        ubicaciones = {}
        for linea in self:
            company = linea.company_id or self.env.company
            if company not in ubicaciones:
                almacen = self.env['stock.warehouse'].search([('company_id', '=', company.id)], limit=1)
                ubicaciones[company] = almacen.lot_stock_id
            producto = linea.producto_id
            if ubicaciones[company]:
                producto = producto.with_context(location=ubicaciones[company].id)
            linea.stock_disponible = producto.qty_available if producto.is_storable else 0

    @api.depends('producto_id')
    def _compute_precio_unitario(self):
        for linea in self:
            linea.precio_unitario = linea.producto_id.lst_price

    @api.depends('cantidad', 'precio_unitario', 'currency_id')
    def _compute_subtotal(self):
        for linea in self:
            subtotal = linea.cantidad * linea.precio_unitario
            linea.subtotal = linea.currency_id.round(subtotal) if linea.currency_id else subtotal

    def _vet_valores_factura(self):
        self.ensure_one()
        return {
            'product_id': self.producto_id.id,
            'quantity': self.cantidad,
            'product_uom_id': self.uom_id.id,
            'price_unit': self.precio_unitario,
        }

    def _vet_verificar_no_cobrada(self):
        cobrados = self._vet_documento().filtered('factura_id')
        if cobrados:
            raise UserError(f'{cobrados[0].name} ya está cobrado: no se pueden cambiar sus servicios ni productos. '
                            'Para corregirlo, emita una nota de crédito desde la factura.')

    @api.model_create_multi
    def create(self, vals_list):
        lineas = super().create(vals_list)
        lineas._vet_verificar_no_cobrada()
        return lineas

    def write(self, vals):
        self._vet_verificar_no_cobrada()
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_excepto_cobradas(self):
        self._vet_verificar_no_cobrada()
