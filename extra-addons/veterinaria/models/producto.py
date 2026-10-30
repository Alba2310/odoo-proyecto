# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.tools import float_compare

AREAS = [
    ('consultorio', 'Consultorio'),
    ('estetica', 'Baño y peluquería'),
    ('internacion', 'Internación y hotel'),
]

APLICACIONES = [
    ('vacuna', 'Vacuna'),
    ('desparasitacion_interna', 'Desparasitación interna'),
    ('desparasitacion_externa', 'Desparasitación externa'),
]


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    vet_area = fields.Selection(AREAS, string='Se usa en',
                                help='Consultorio y Baño y peluquería: se ofrece en la agenda de esa área. '
                                     'Internación y hotel: se cobra por día de estadía.')
    vet_duracion = fields.Integer('Duración del turno (min)',
                                  help='Cuánto ocupa en la agenda. Con esto se calcula cuándo termina el turno.')
    vet_reserva_online = fields.Boolean('Se reserva por internet',
                                        help='Aparece en la página de turnos para que el dueño lo pida solo.')
    vet_especie_ids = fields.Many2many('vet.especie', string='Para',
                                       help='Especies para las que se ofrece en la página de turnos. Vacío: todas.')
    vet_aplicacion = fields.Selection(APLICACIONES, string='Es una',
                                      help='Al terminar la atención queda anotada en el carnet de la mascota, con la '
                                           'fecha de la próxima dosis.')
    vet_dias_refuerzo = fields.Integer('Próxima dosis a los (días)',
                                       help='Por ejemplo 365 para una vacuna anual o 90 para la desparasitación cada '
                                            'tres meses. Cero: no se repite.')

    # Stock mínimo: se guarda en la regla de reabastecimiento de Odoo (stock.warehouse.orderpoint) del depósito,
    # así el producto aparece en Compras › Para reponer y se pide al proveedor desde ahí.
    vet_stock_minimo = fields.Float('Stock mínimo', compute='_compute_vet_reposicion',
                                    inverse='_inverse_vet_reposicion', digits='Product Unit of Measure',
                                    help='Cuando el stock baja de esta cantidad, aparece en Para reponer.')
    vet_stock_maximo = fields.Float('Pedir hasta', compute='_compute_vet_reposicion',
                                    inverse='_inverse_vet_reposicion', digits='Product Unit of Measure',
                                    help='Cantidad a la que se quiere llegar al reponer: con esto se calcula cuánto '
                                         'pedir.')
    vet_por_reponer = fields.Boolean('Por reponer', compute='_compute_vet_por_reponer')

    _sql_constraints = [
        ('vet_duracion_positiva', 'CHECK(vet_duracion >= 0)', 'La duración no puede ser negativa.'),
        ('vet_refuerzo_positivo', 'CHECK(vet_dias_refuerzo >= 0)', 'Los días de la próxima dosis no pueden ser '
                                                                    'negativos.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        productos = super().create(vals_list)
        # La regla de stock mínimo necesita la variante del producto, que se crea después del producto.
        for producto, vals in zip(productos, vals_list):
            reposicion = {campo: vals[campo] for campo in ('vet_stock_minimo', 'vet_stock_maximo') if campo in vals}
            if reposicion:
                producto.write(reposicion)
        return productos

    def _vet_almacen(self):
        return self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)

    def _vet_regla_reposicion(self):
        self.ensure_one()
        if not self.product_variant_ids.ids:
            return self.env['stock.warehouse.orderpoint']
        return self.env['stock.warehouse.orderpoint'].search([
            ('product_id', 'in', self.product_variant_ids.ids),
            ('warehouse_id', '=', self._vet_almacen().id),
        ], limit=1)

    @api.depends('product_variant_ids.orderpoint_ids.product_min_qty',
                 'product_variant_ids.orderpoint_ids.product_max_qty')
    def _compute_vet_reposicion(self):
        for producto in self:
            regla = producto._vet_regla_reposicion()
            producto.vet_stock_minimo = regla.product_min_qty
            producto.vet_stock_maximo = regla.product_max_qty

    def _inverse_vet_reposicion(self):
        for producto in self:
            if not producto.product_variant_id:
                continue  # Recién creado: create() lo vuelve a guardar cuando ya tiene variante.
            minimo = producto.vet_stock_minimo
            valores = {'product_min_qty': minimo, 'product_max_qty': max(producto.vet_stock_maximo, minimo)}
            regla = producto._vet_regla_reposicion()
            if regla:
                regla.write(valores)
            elif minimo or producto.vet_stock_maximo:
                almacen = producto._vet_almacen()
                self.env['stock.warehouse.orderpoint'].create({
                    'product_id': producto.product_variant_id.id,
                    'warehouse_id': almacen.id,
                    'location_id': almacen.lot_stock_id.id,
                    'trigger': 'manual',
                    **valores,
                })

    @api.depends('is_storable', 'qty_available', 'vet_stock_minimo')
    def _compute_vet_por_reponer(self):
        for producto in self:
            producto.vet_por_reponer = bool(
                producto.is_storable and producto.vet_stock_minimo > 0
                and float_compare(producto.qty_available, producto.vet_stock_minimo,
                                  precision_rounding=producto.uom_id.rounding or 0.01) < 0)

    @api.model
    def _vet_por_reponer(self):
        """Productos que bajaron del stock mínimo en el depósito de la compañía activa."""
        reglas = self.env['stock.warehouse.orderpoint'].search([
            ('product_min_qty', '>', 0),
            ('warehouse_id.company_id', '=', self.env.company.id),
        ])
        return reglas.product_id.product_tmpl_id.filtered('vet_por_reponer')
