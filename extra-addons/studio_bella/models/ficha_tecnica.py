# -*- coding: utf-8 -*-
from odoo import api, fields, models

TIPOS_FICHA = [
    ('color', 'Color'),
    ('mechas', 'Mechas / decoloración'),
    ('alisado', 'Alisado / keratina'),
    ('tratamiento', 'Tratamiento'),
    ('otro', 'Otro'),
]


class BellaFichaTecnica(models.Model):
    """Lo que se le hizo a la clienta y con qué: fórmula, productos, tiempo de pose y resultado.

    Sirve para repetir el mismo trabajo en la próxima visita, aunque la atienda otra estilista.
    """
    _name = 'bella.ficha.tecnica'
    _description = 'Ficha técnica'
    _order = 'fecha desc, id desc'
    _check_company_auto = True

    name = fields.Char('Trabajo', compute='_compute_name', store=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                 default=lambda self: self.env.company)
    cita_id = fields.Many2one('bella.cita', string='Cita', ondelete='set null', index=True, check_company=True)
    # Si la ficha se carga desde la cita, la clienta, la estilista y el día salen de ahí.
    cliente_id = fields.Many2one('res.partner', string='Cliente', required=True, index=True, check_company=True,
                                 compute='_compute_desde_cita', store=True, readonly=False, precompute=True)
    estilista_id = fields.Many2one('hr.employee', string='Estilista', check_company=True,
                                   domain=[('bella_estilista', '=', True)],
                                   compute='_compute_desde_cita', store=True, readonly=False, precompute=True)
    fecha = fields.Date('Fecha', required=True, compute='_compute_desde_cita', store=True, readonly=False,
                        precompute=True)
    tipo = fields.Selection(TIPOS_FICHA, string='Tipo', required=True, default='color')
    formula = fields.Text('Fórmula y productos', required=True,
                          help='Por ejemplo: 6.0 + 6.1 en partes iguales (30 g c/u), oxidante 20 vol 60 ml.')
    tiempo_pose = fields.Integer('Tiempo de pose (min)')
    resultado = fields.Text('Resultado y observaciones',
                            help='Cómo quedó y qué cambiar la próxima vez.')
    foto = fields.Image('Foto del resultado', max_width=1024, max_height=1024)

    @api.depends('tipo', 'fecha')
    def _compute_name(self):
        tipos = dict(TIPOS_FICHA)
        for ficha in self:
            fecha = ficha.fecha.strftime('%d/%m/%Y') if ficha.fecha else ''
            ficha.name = ' · '.join(parte for parte in (tipos.get(ficha.tipo), fecha) if parte)

    @api.depends('cita_id')
    def _compute_desde_cita(self):
        for ficha in self:
            cita = ficha.cita_id
            if cita:
                ficha.cliente_id = cita.cliente_id
                ficha.estilista_id = cita.estilista_id
                ficha.fecha = cita._dia_local(cita.fecha_inicio) if cita.fecha_inicio else fields.Date.context_today(ficha)
            else:
                ficha.cliente_id = ficha.cliente_id
                ficha.estilista_id = ficha.estilista_id
                ficha.fecha = ficha.fecha or fields.Date.context_today(ficha)
