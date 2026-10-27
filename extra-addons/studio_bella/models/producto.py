# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare

# Resumen de la actividad que avisa que hay que reponer un producto.
RESUMEN_REPONER = 'Reponer stock'


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    bella_duracion = fields.Integer('Duración (min)', default=30,
                                    help='Tiempo que lleva el servicio. Con esto se calcula cuándo termina la cita.')
    bella_insumo_ids = fields.One2many('bella.servicio.insumo', 'servicio_tmpl_id', string='Insumos que usa',
                                       help='Productos que se gastan cada vez que se hace el servicio. '
                                            'Se descuentan del stock al cobrar la cita.')

    # Stock mínimo: se guarda en la regla de reabastecimiento de Odoo (stock.warehouse.orderpoint) del depósito
    # principal, así el producto aparece en Reposición y se puede pedir al proveedor con un clic.
    bella_stock_minimo = fields.Float('Stock mínimo', compute='_compute_bella_reposicion',
                                      inverse='_inverse_bella_reposicion', digits='Product Unit of Measure',
                                      help='Cuando el stock baja de esta cantidad, el sistema avisa que hay que reponer.')
    bella_stock_maximo = fields.Float('Pedir hasta', compute='_compute_bella_reposicion',
                                      inverse='_inverse_bella_reposicion', digits='Product Unit of Measure',
                                      help='Cantidad a la que se quiere llegar al reponer: con esto se calcula cuánto pedir.')
    bella_por_reponer = fields.Boolean('Por reponer', compute='_compute_bella_por_reponer',
                                       search='_search_bella_por_reponer')

    _sql_constraints = [
        ('bella_duracion_positiva', 'CHECK(bella_duracion >= 0)', 'La duración no puede ser negativa.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        productos = super().create(vals_list)
        # La regla de stock mínimo necesita la variante del producto, que se crea después del producto.
        for producto, vals in zip(productos, vals_list):
            reposicion = {campo: vals[campo] for campo in ('bella_stock_minimo', 'bella_stock_maximo') if campo in vals}
            if reposicion:
                producto.write(reposicion)
        return productos

    def _bella_almacen(self):
        return self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)

    def _bella_regla_reposicion(self):
        """Regla de stock mínimo del producto en el depósito principal."""
        self.ensure_one()
        if not self.product_variant_ids.ids:
            return self.env['stock.warehouse.orderpoint']
        return self.env['stock.warehouse.orderpoint'].search([
            ('product_id', 'in', self.product_variant_ids.ids),
            ('warehouse_id', '=', self._bella_almacen().id),
        ], limit=1)

    @api.depends('product_variant_ids.orderpoint_ids.product_min_qty',
                 'product_variant_ids.orderpoint_ids.product_max_qty')
    def _compute_bella_reposicion(self):
        for producto in self:
            regla = producto._bella_regla_reposicion()
            producto.bella_stock_minimo = regla.product_min_qty
            producto.bella_stock_maximo = regla.product_max_qty

    def _inverse_bella_reposicion(self):
        for producto in self:
            if not producto.product_variant_id:
                continue  # Producto recién creado: create() lo vuelve a guardar cuando ya tiene variante.
            minimo = producto.bella_stock_minimo
            valores = {'product_min_qty': minimo, 'product_max_qty': max(producto.bella_stock_maximo, minimo)}
            regla = producto._bella_regla_reposicion()
            if regla:
                regla.write(valores)
            elif minimo or producto.bella_stock_maximo:
                almacen = producto._bella_almacen()
                self.env['stock.warehouse.orderpoint'].create({
                    'product_id': producto.product_variant_id.id,
                    'warehouse_id': almacen.id,
                    'location_id': almacen.lot_stock_id.id,
                    'trigger': 'manual',
                    **valores,
                })

    @api.depends('is_storable', 'qty_available', 'bella_stock_minimo')
    def _compute_bella_por_reponer(self):
        for producto in self:
            producto.bella_por_reponer = bool(
                producto.is_storable and producto.bella_stock_minimo > 0
                and float_compare(producto.qty_available, producto.bella_stock_minimo,
                                  precision_rounding=producto.uom_id.rounding or 0.01) < 0)

    def _search_bella_por_reponer(self, operator, value):
        if operator not in ('=', '!=') or not isinstance(value, bool):
            raise UserError('Búsqueda no permitida en "Por reponer".')
        reglas = self.env['stock.warehouse.orderpoint'].search([('product_min_qty', '>', 0)])
        ids = reglas.product_id.product_tmpl_id.filtered('bella_por_reponer').ids
        return [('id', 'in' if (operator == '=') == value else 'not in', ids)]

    @api.model
    def _bella_avisar_reposicion(self, productos=None):
        """Deja la actividad "Reponer stock" en los productos que bajaron del mínimo
        y la da por hecha en los que ya se repusieron. Sin productos, revisa todos los que tienen mínimo."""
        if productos is None:
            productos = self.env['stock.warehouse.orderpoint'].search(
                [('product_min_qty', '>', 0)]).product_id.product_tmpl_id
        # sudo: lo llama quien cobra o recibe mercadería, que no edita productos.
        for producto in productos.sudo():
            abiertas = producto.activity_ids.filtered(lambda actividad: actividad.summary == RESUMEN_REPONER)
            if producto.bella_por_reponer and not abiertas:
                faltan = producto.bella_stock_maximo - producto.qty_available
                producto.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=RESUMEN_REPONER,
                    note=f'Quedan {producto.qty_available:g} {producto.uom_id.name} y el mínimo es '
                         f'{producto.bella_stock_minimo:g}. Conviene pedir {faltan:g} para llegar a '
                         f'{producto.bella_stock_maximo:g}.',
                    user_id=(producto.responsible_id or self.env.ref('base.user_admin')).id,
                )
            elif abiertas and not producto.bella_por_reponer:
                abiertas.action_feedback(feedback='Stock repuesto.')


class BellaServicioInsumo(models.Model):
    _name = 'bella.servicio.insumo'
    _description = 'Insumo de un servicio'
    _order = 'servicio_tmpl_id, id'

    servicio_tmpl_id = fields.Many2one('product.template', string='Servicio', required=True,
                                       ondelete='cascade', index=True)
    producto_id = fields.Many2one('product.product', string='Insumo', required=True,
                                  domain=lambda self: self._domain_insumos())
    cantidad = fields.Float('Cantidad por servicio', default=1, required=True, digits='Product Unit of Measure')
    uom_id = fields.Many2one(related='producto_id.uom_id', string='Unidad')

    _sql_constraints = [
        ('cantidad_positiva', 'CHECK(cantidad > 0)', 'La cantidad del insumo debe ser mayor que cero.'),
    ]

    @api.model
    def _domain_insumos(self):
        # Cualquier producto de la peluquería con stock: de uso profesional o de reventa.
        domain = [('type', '=', 'consu')]
        categoria = self.env.ref('studio_bella.categoria_productos', raise_if_not_found=False)
        return domain + [('categ_id', 'child_of', categoria.id)] if categoria else domain
