# -*- coding: utf-8 -*-
from odoo import fields, models, tools

TIPOS_MOVIMIENTO = [
    ('ingreso', 'Cobrado'),
    ('gasto', 'Gasto'),
]


class AlquilerResultado(models.Model):
    """Lo cobrado y lo gastado en cada propiedad, para ver la ganancia real por mes (solo lectura)."""
    _name = 'alquiler.resultado'
    _description = 'Ingresos y gastos'
    _auto = False
    _order = 'fecha desc'

    fecha = fields.Date('Fecha', readonly=True)
    tipo = fields.Selection(TIPOS_MOVIMIENTO, string='Tipo', readonly=True)
    concepto = fields.Char('Concepto', readonly=True)
    propiedad_id = fields.Many2one('alquiler.propiedad', string='Propiedad', readonly=True)
    unidad_id = fields.Many2one('alquiler.unidad', string='Unidad', readonly=True)
    company_id = fields.Many2one('res.company', string='Compañía', readonly=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    ingreso = fields.Monetary('Cobrado', readonly=True)
    gasto = fields.Monetary('Gastos', readonly=True)
    ganancia = fields.Monetary('Ganancia', readonly=True)

    def init(self):
        # El depósito es del inquilino mientras dura el contrato: no es ingreso cuando se cobra ni cuando se
        # devuelve. Lo que se usa al terminar sí lo es, el día que se usa: las cuotas que se pagan con él (pagos con
        # medio "deposito") y el descuento por daños que se retiene.
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE VIEW {self._table} AS (
                SELECT pago.id * 3 AS id, pago.fecha, 'ingreso' AS tipo,
                       pago.name || ' · ' || cuota.name
                           || CASE WHEN pago.medio = 'deposito' THEN ' (con el depósito)' ELSE '' END AS concepto,
                       pago.propiedad_id, pago.unidad_id, pago.company_id,
                       pago.monto AS ingreso, 0 AS gasto, pago.monto AS ganancia
                  FROM alquiler_pago pago
                  JOIN alquiler_cuota cuota ON cuota.id = pago.cuota_id
                UNION ALL
                SELECT gasto.id * 3 + 1, gasto.fecha, 'gasto', gasto.name,
                       gasto.propiedad_id, gasto.unidad_id, gasto.company_id,
                       0, gasto.monto, -gasto.monto
                  FROM alquiler_gasto gasto
                UNION ALL
                SELECT contrato.id * 3 + 2, contrato.fecha_fin, 'ingreso',
                       'Descuento del depósito por daños · ' || contrato.name,
                       contrato.propiedad_id, contrato.unidad_id, contrato.company_id,
                       contrato.deposito_descuento, 0, contrato.deposito_descuento
                  FROM alquiler_contrato contrato
                 WHERE contrato.estado = 'terminado' AND contrato.deposito_descuento > 0
            )""")
