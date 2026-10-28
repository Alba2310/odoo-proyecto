# -*- coding: utf-8 -*-
from collections import defaultdict

from markupsafe import Markup

from odoo import Command, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare

METODOS_PAGO = [
    ('efectivo', 'Efectivo'),
    ('tarjeta', 'Tarjeta'),
    ('transferencia', 'Transferencia / QR'),
]


class BellaCobroMixin(models.AbstractModel):
    """Lo que comparten la cita y la venta de mostrador al cobrar: factura, pago y descuento de stock.

    El modelo que lo hereda tiene que tener los campos ``name``, ``company_id`` y ``cliente_id``,
    heredar ``mail.thread`` y definir ``_bella_lineas_factura`` y ``_bella_productos_vendidos``.
    """
    _name = 'bella.cobro.mixin'
    _description = 'Cobro con factura'

    factura_id = fields.Many2one('account.move', string='Factura', readonly=True, copy=False)
    estado_pago = fields.Selection(related='factura_id.payment_state', string='Estado de pago')
    metodo_pago = fields.Selection(METODOS_PAGO, string='Forma de pago', readonly=True, copy=False)
    movimiento_ids = fields.Many2many('stock.move', string='Movimientos de stock', readonly=True, copy=False)
    movimiento_count = fields.Integer(compute='_compute_movimiento_count')

    def _compute_movimiento_count(self):
        for documento in self:
            documento.movimiento_count = len(documento.movimiento_ids)

    # Lo que define cada documento

    def _bella_lineas_factura(self):
        """Comandos ``Command.create`` con las líneas de la factura."""
        raise NotImplementedError()

    def _bella_productos_vendidos(self):
        """Líneas de productos que se le venden al cliente (modelos que heredan ``bella.linea.producto``)."""
        raise NotImplementedError()

    def _bella_insumos(self):
        """Productos que se gastan al hacer el trabajo y no se cobran aparte: ``{producto: cantidad}``."""
        return {}

    # Cobro

    def _bella_cobrar(self, metodo_pago, diario=None, fecha=None):
        """Emite la factura, registra el pago y descuenta del stock lo vendido y lo usado."""
        self.ensure_one()
        if self.factura_id:
            raise UserError(f'{self.name} ya está cobrado con la factura {self.factura_id.name}.')
        lineas = self._bella_lineas_factura()
        if not lineas:
            raise UserError('No hay nada para cobrar: cargue al menos un servicio o un producto.')
        self._bella_verificar_stock()
        diario = diario or self._bella_diario(metodo_pago)
        fecha = fecha or fields.Date.context_today(self)
        self.env['bella.cierre.caja']._verificar_caja_abierta(self.company_id, fecha)

        factura = self.env['account.move'].with_company(self.company_id).create({
            'move_type': 'out_invoice',
            'partner_id': self.cliente_id.id,
            'invoice_date': fecha,
            'invoice_origin': self.name,
            'invoice_user_id': self.env.user.id,
            'company_id': self.company_id.id,
            'invoice_line_ids': lineas,
        })
        factura.action_post()
        # Una factura en cero (por ejemplo, un servicio de cortesía) no tiene nada que pagar.
        if not factura.currency_id.is_zero(factura.amount_residual):
            self.env['account.payment.register'].with_context(
                active_model='account.move', active_ids=factura.ids,
            ).create({'journal_id': diario.id, 'payment_date': fecha})._create_payments()

        self.write({'factura_id': factura.id, 'metodo_pago': metodo_pago})
        self.env['bella.cierre.caja']._actualizar_dia(self.company_id, fecha)
        self._bella_descontar_stock()
        self.message_post(body=Markup('Cobrado (%s) con la factura %s.') % (
            dict(METODOS_PAGO)[metodo_pago], factura._get_html_link()))
        return factura

    def _bella_buscar_diario(self, metodo_pago):
        """El efectivo entra a la caja; la tarjeta y la transferencia, al banco."""
        tipo = 'cash' if metodo_pago == 'efectivo' else 'bank'
        return self.env['account.journal'].search([
            ('company_id', '=', self.company_id.id),
            ('type', '=', tipo),
        ], limit=1)

    def _bella_diario(self, metodo_pago):
        diario = self._bella_buscar_diario(metodo_pago)
        if not diario:
            tipo = 'efectivo' if metodo_pago == 'efectivo' else 'banco'
            raise UserError(f'No hay un diario de {tipo} en Facturación para registrar el pago.')
        return diario

    # Stock

    def _bella_almacen(self):
        almacen = self.env['stock.warehouse'].search([('company_id', '=', self.company_id.id)], limit=1)
        if not almacen:
            raise UserError(f'{self.company_id.name} no tiene un depósito en Inventario.')
        return almacen

    def _bella_cantidades_vendidas(self):
        """Lo vendido sumado por producto, solo de los productos con control de stock."""
        cantidades = defaultdict(float)
        for linea in self._bella_productos_vendidos():
            if linea.producto_id.is_storable:
                cantidades[linea.producto_id] += linea.cantidad
        return cantidades

    def _bella_verificar_stock(self):
        """No se cobra un producto que no figura en el depósito: primero hay que corregir el inventario.

        Los insumos de los servicios no frenan el cobro (el cliente ya fue atendido): si faltan,
        el stock queda en negativo y se avisa en el historial.
        """
        ubicacion = self._bella_almacen().lot_stock_id
        faltantes = []
        for producto, cantidad in self._bella_cantidades_vendidas().items():
            disponible = producto.with_context(location=ubicacion.id).qty_available
            if float_compare(cantidad, disponible, precision_rounding=producto.uom_id.rounding) > 0:
                faltantes.append(f'• {producto.display_name}: se venden {cantidad:g} y hay {disponible:g}')
        if faltantes:
            raise UserError('No hay stock suficiente para cobrar:\n' + '\n'.join(faltantes)
                            + '\nCargue el stock en Inventario o quite el producto.')

    def _bella_descontar_stock(self):
        """Saca del depósito lo vendido (va al cliente) y los insumos usados (consumo interno)."""
        origen = self._bella_almacen().lot_stock_id
        clientes = self.env.ref('stock.stock_location_customers')
        valores = [
            self._bella_valores_movimiento(producto, cantidad, origen, clientes)
            for producto, cantidad in self._bella_cantidades_vendidas().items()
        ]
        insumos = {producto: cantidad for producto, cantidad in self._bella_insumos().items()
                   if producto.is_storable}
        for producto, cantidad in insumos.items():
            consumo = producto.with_company(self.company_id).property_stock_inventory
            valores.append(self._bella_valores_movimiento(producto, cantidad, origen, consumo))
        if not valores:
            return

        movimientos = self.env['stock.move'].create(valores)._action_confirm()
        movimientos._action_assign()
        for movimiento in movimientos:
            movimiento.quantity = movimiento.product_uom_qty
        movimientos.picked = True
        movimientos._action_done()
        self.movimiento_ids = [Command.link(movimiento.id) for movimiento in movimientos]

        en_negativo = [producto.display_name for producto in insumos
                       if producto.with_context(location=origen.id).qty_available < 0]
        if en_negativo:
            self.message_post(body='Quedó stock negativo de: ' + ', '.join(en_negativo)
                              + '. Revise el inventario de insumos.')
        self.env['product.template']._bella_avisar_reposicion(movimientos.product_id.product_tmpl_id)

    def _bella_valores_movimiento(self, producto, cantidad, origen, destino):
        return {
            'name': f'{self.name}: {producto.display_name}',
            'origin': self.name,
            'product_id': producto.id,
            'product_uom': producto.uom_id.id,
            'product_uom_qty': cantidad,
            'location_id': origen.id,
            'location_dest_id': destino.id,
            'partner_id': self.cliente_id.id,
            'company_id': self.company_id.id,
        }

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


class BellaLineaProducto(models.AbstractModel):
    """Producto que se le vende al cliente; lo usan la cita y la venta de mostrador.

    Cada modelo concreto redefine ``company_id`` y ``currency_id`` como campos relacionados con su documento.
    """
    _name = 'bella.linea.producto'
    _description = 'Producto vendido'

    sequence = fields.Integer(default=10)
    company_id = fields.Many2one('res.company', string='Compañía')
    currency_id = fields.Many2one('res.currency', string='Moneda')
    producto_id = fields.Many2one('product.product', string='Producto', required=True, check_company=True,
                                  domain=lambda self: self._domain_productos())
    cantidad = fields.Float('Cantidad', default=1, required=True, digits='Product Unit of Measure')
    uom_id = fields.Many2one(related='producto_id.uom_id', string='Unidad')
    stock_disponible = fields.Float('En stock', compute='_compute_stock_disponible',
                                    digits='Product Unit of Measure')
    precio_unitario = fields.Monetary('Precio unitario', compute='_compute_precio_unitario',
                                      store=True, readonly=False, precompute=True)
    subtotal = fields.Monetary('Subtotal', compute='_compute_subtotal', store=True)

    _sql_constraints = [
        ('cantidad_positiva', 'CHECK(cantidad > 0)', 'La cantidad vendida debe ser mayor que cero.'),
    ]

    @api.model
    def _domain_productos(self):
        # Solo los productos de reventa de la peluquería, no los insumos de uso profesional.
        domain = [('type', '=', 'consu'), ('sale_ok', '=', True)]
        categoria = self.env.ref('studio_bella.categoria_productos', raise_if_not_found=False)
        return domain + [('categ_id', 'child_of', categoria.id)] if categoria else domain

    @api.depends('producto_id', 'company_id')
    def _compute_stock_disponible(self):
        ubicaciones = {}
        for linea in self:
            company = linea.company_id or self.env.company
            if company not in ubicaciones:
                almacen = self.env['stock.warehouse'].search([('company_id', '=', company.id)], limit=1)
                ubicaciones[company] = almacen.lot_stock_id
            ubicacion = ubicaciones[company]
            producto = linea.producto_id.with_context(location=ubicacion.id) if ubicacion else linea.producto_id
            linea.stock_disponible = producto.qty_available

    @api.depends('producto_id')
    def _compute_precio_unitario(self):
        for linea in self:
            linea.precio_unitario = linea.producto_id.lst_price

    @api.depends('cantidad', 'precio_unitario', 'currency_id')
    def _compute_subtotal(self):
        for linea in self:
            subtotal = linea.cantidad * linea.precio_unitario
            linea.subtotal = linea.currency_id.round(subtotal) if linea.currency_id else subtotal

    def _bella_valores_linea_factura(self):
        self.ensure_one()
        return {
            'product_id': self.producto_id.id,
            'quantity': self.cantidad,
            'product_uom_id': self.uom_id.id,
            'price_unit': self.precio_unitario,
        }
