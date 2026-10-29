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
    factura_moneda_id = fields.Many2one(related='factura_id.currency_id', string='Moneda de la factura')
    # Lo que pagó la clienta: el total menos el descuento por puntos, si usó.
    monto_cobrado = fields.Monetary(related='factura_id.amount_total', string='Cobrado',
                                    currency_field='factura_moneda_id')
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

    def _bella_cobrar(self, metodo_pago, diario=None, fecha=None, puntos=0):
        """Emite la factura, registra el pago y descuenta del stock lo vendido y lo usado.

        ``puntos``: los que la clienta usa como descuento (ver ``_bella_descontar_puntos``).
        """
        self.ensure_one()
        if self.factura_id:
            raise UserError(f'{self.name} ya está cobrado con la factura {self.factura_id.name}.')
        lineas = self._bella_lineas_factura()
        if not lineas:
            raise UserError('No hay nada para cobrar: cargue al menos un servicio o un producto.')
        self._bella_verificar_stock()
        if puntos:
            self._bella_verificar_puntos(puntos)
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
        if puntos:
            self._bella_descontar_puntos(factura, puntos, fecha)
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
        self._bella_sumar_puntos(factura, fecha)
        return factura

    # Programa de puntos

    def _bella_suma_puntos(self):
        """El programa está activo y el cliente es una persona (no "Consumidor final")."""
        consumidor_final = self.env.ref('studio_bella.cliente_consumidor_final', raise_if_not_found=False)
        return self.company_id.bella_puntos_activo and self.cliente_id != consumidor_final

    def _bella_verificar_puntos(self, puntos):
        if not self._bella_suma_puntos():
            raise UserError('El programa de puntos no está activo para este cobro.')
        disponibles = self.cliente_id.sudo().bella_puntos
        if puntos < 0 or puntos > disponibles:
            raise UserError(f'{self.cliente_id.name} tiene {disponibles} puntos: no puede usar {puntos}.')

    def _bella_descontar_puntos(self, factura, puntos, fecha):
        """Agrega a la factura (en borrador) el descuento por los puntos usados y los resta del saldo.

        El descuento se reparte entre las tasas de IVA de la factura, en proporción a lo que suma cada una, con una
        línea negativa por tasa: así el IVA de la factura queda calculado sobre lo que de verdad se cobra.
        """
        moneda = factura.currency_id
        descuento = puntos * self.company_id.bella_puntos_valor
        lineas = factura.invoice_line_ids.filtered(lambda linea: linea.display_type == 'product')
        total = sum(lineas.mapped('price_total'))
        if moneda.compare_amounts(descuento, total) > 0:
            raise UserError(f'{puntos} puntos son más que el total a cobrar: use menos puntos.')

        por_impuestos = defaultdict(lambda: self.env['account.move.line'])
        for linea in lineas:
            por_impuestos[linea.tax_ids] |= linea
        grupos = [(impuestos, grupo) for impuestos, grupo in por_impuestos.items()
                  if not moneda.is_zero(sum(grupo.mapped('price_total')))]
        restante = descuento
        nuevas = []
        for indice, (impuestos, grupo) in enumerate(grupos):
            total_grupo = sum(grupo.mapped('price_total'))
            parte = restante if indice == len(grupos) - 1 else moneda.round(descuento * total_grupo / total)
            restante -= parte
            if all(impuesto.price_include for impuesto in impuestos):
                precio = parte  # IVA incluido en el precio, como en Paraguay.
            else:
                precio = moneda.round(parte * sum(grupo.mapped('price_subtotal')) / total_grupo)
            nuevas.append(Command.create({
                'name': f'Descuento por {puntos} puntos',
                'quantity': 1,
                'price_unit': -precio,
                'tax_ids': [Command.set(impuestos.ids)],
                'account_id': grupo[0].account_id.id,
            }))
        factura.invoice_line_ids = nuevas
        self.env['bella.puntos'].sudo().create({
            'company_id': self.company_id.id,
            'cliente_id': self.cliente_id.id,
            'fecha': fecha,
            'puntos': -puntos,
            'concepto': f'Usados en {self.name}',
            'factura_id': factura.id,
        })

    def _bella_sumar_puntos(self, factura, fecha):
        """La clienta gana un punto por cada "Monto por punto" que pagó (sin contar lo que pagó con puntos)."""
        company = self.company_id
        if not self._bella_suma_puntos() or company.currency_id.compare_amounts(company.bella_puntos_monto, 0) <= 0:
            return
        ganados = int(factura.amount_total // company.bella_puntos_monto)
        if not ganados:
            return
        self.env['bella.puntos'].sudo().create({
            'company_id': company.id,
            'cliente_id': self.cliente_id.id,
            'fecha': fecha,
            'puntos': ganados,
            'concepto': f'Ganados en {self.name}',
            'factura_id': factura.id,
        })
        self.message_post(body=f'{self.cliente_id.name} ganó {ganados} puntos. '
                               f'Ahora tiene {self.cliente_id.sudo().bella_puntos}.')

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
