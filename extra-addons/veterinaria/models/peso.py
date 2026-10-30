# -*- coding: utf-8 -*-
from odoo import api, fields, models


class VetPeso(models.Model):
    """Cada vez que se pesa a la mascota: en una consulta, en un control de internación o a mano."""
    _name = 'vet.peso'
    _description = 'Peso de la mascota'
    _order = 'fecha desc, id desc'

    mascota_id = fields.Many2one('vet.mascota', string='Mascota', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='mascota_id.company_id', store=True)
    fecha = fields.Date('Fecha', required=True, default=fields.Date.context_today)
    peso = fields.Float('Peso (kg)', required=True, digits=(6, 2))
    origen = fields.Char('Dónde se pesó')
    atencion_id = fields.Many2one('vet.atencion', string='Atención', ondelete='cascade', index='btree_not_null')
    control_id = fields.Many2one('vet.control', string='Control', ondelete='cascade', index='btree_not_null')

    _sql_constraints = [
        ('peso_positivo', 'CHECK(peso > 0)', 'El peso tiene que ser mayor que cero.'),
    ]


class VetRegistraPeso(models.AbstractModel):
    """La atención y el control de internación anotan el peso en el historial de la mascota.

    El modelo que lo hereda tiene ``mascota_id`` y ``peso`` y define ``_vet_datos_peso`` (fecha y origen); en
    ``vet.peso`` hay un campo que apunta a él (``_vet_campo_peso``).
    """
    _name = 'vet.registra.peso'
    _description = 'Anota el peso de la mascota'

    _vet_campo_peso = None

    def _vet_datos_peso(self):
        raise NotImplementedError()

    @api.model_create_multi
    def create(self, vals_list):
        registros = super().create(vals_list)
        registros._vet_guardar_peso()
        return registros

    def write(self, vals):
        res = super().write(vals)
        if {'peso', 'mascota_id'} & set(vals) or self._vet_cambia_fecha_peso(vals):
            self._vet_guardar_peso()
        return res

    def _vet_cambia_fecha_peso(self, vals):
        return False

    def _vet_guardar_peso(self):
        Peso = self.env['vet.peso'].sudo()
        for registro in self:
            anterior = Peso.search([(self._vet_campo_peso, '=', registro.id)])
            if not registro.peso or registro.peso <= 0:
                anterior.unlink()
                continue
            valores = {'mascota_id': registro.mascota_id.id, 'peso': registro.peso, **registro._vet_datos_peso()}
            if anterior:
                anterior.write(valores)
            else:
                Peso.create({self._vet_campo_peso: registro.id, **valores})
