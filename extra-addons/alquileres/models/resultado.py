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
        # Los pagos con el depósito no son plata nueva: el depósito ya se había cobrado al empezar.
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE VIEW {self._table} AS (
                SELECT pago.id * 2 AS id, pago.fecha, 'ingreso' AS tipo,
                       pago.name || ' · ' || cuota.name AS concepto,
                       pago.propiedad_id, pago.unidad_id, pago.company_id,
                       pago.monto AS ingreso, 0 AS gasto, pago.monto AS ganancia
                  FROM alquiler_pago pago
                  JOIN alquiler_cuota cuota ON cuota.id = pago.cuota_id
                 WHERE pago.medio != 'deposito'
                UNION ALL
                SELECT gasto.id * 2 + 1, gasto.fecha, 'gasto', gasto.name,
                       gasto.propiedad_id, gasto.unidad_id, gasto.company_id,
                       0, gasto.monto, -gasto.monto
                  FROM alquiler_gasto gasto
            )""")
