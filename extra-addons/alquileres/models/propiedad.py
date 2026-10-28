# -*- coding: utf-8 -*-
from odoo import api, fields, models

from .utiles import guaranies

TIPOS_PROPIEDAD = [
    ('casa', 'Casa'),
    ('edificio', 'Edificio de departamentos'),
    ('local', 'Local comercial'),
    ('otro', 'Otro'),
]
ESTADOS_UNIDAD = [
    ('libre', 'Libre'),
    ('alquilada', 'Alquilada'),
]
# Color de cada unidad en el tablero de control (colores de Odoo: 1 rojo, 3 amarillo, 10 verde).
COLOR_LIBRE, COLOR_CON_DEUDA, COLOR_POR_VENCER, COLOR_AL_DIA = 0, 1, 3, 10
DIAS_POR_VENCER = 3


class AlquilerPropiedad(models.Model):
    """Una casa o un edificio. Lo que se alquila son sus unidades: una casa tiene una sola, que se crea sola,
    y un edificio, una por departamento."""
    _name = 'alquiler.propiedad'
    _description = 'Propiedad'
    _inherit = ['mail.thread']
    _order = 'sequence, name'

    name = fields.Char('Nombre', required=True, tracking=True, help='Por ejemplo: Casa Caacupé, Edificio Ypacaraí.')
    sequence = fields.Integer('Orden', default=10)
    active = fields.Boolean('Activa', default=True)
    tipo = fields.Selection(TIPOS_PROPIEDAD, string='Tipo', required=True, default='casa')
    ciudad = fields.Char('Ciudad', required=True, tracking=True)
    direccion = fields.Char('Dirección')
    propietario_id = fields.Many2one('res.partner', string='Dueño', tracking=True,
                                     help='Firma los recibos de los alquileres de esta propiedad. Si está vacío, '
                                          'firma la empresa.')
    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    foto = fields.Image('Foto', max_width=1024, max_height=1024)
    nota = fields.Text('Notas')
    unidad_ids = fields.One2many('alquiler.unidad', 'propiedad_id', string='Unidades')
    unidades_total = fields.Integer('Cantidad de unidades', compute='_compute_ocupacion')
    unidades_alquiladas = fields.Integer('Alquiladas', compute='_compute_ocupacion')
    ocupacion = fields.Char('Ocupación', compute='_compute_ocupacion')
    alquiler_mensual = fields.Monetary('Alquileres por mes', compute='_compute_ocupacion',
                                       help='Suma de los alquileres de los contratos vigentes.')
    deuda = fields.Monetary('Deuda', compute='_compute_deuda', help='Cuotas vencidas sin pagar de sus inquilinos.')

    @api.model_create_multi
    def create(self, vals_list):
        propiedades = super().create(vals_list)
        # Una casa se alquila entera: su única unidad se crea sola.
        for propiedad in propiedades.filtered(lambda p: p.tipo == 'casa' and not p.unidad_ids):
            self.env['alquiler.unidad'].create({'name': 'Casa', 'propiedad_id': propiedad.id})
        return propiedades

    @api.depends('unidad_ids.estado', 'unidad_ids.contrato_id.monto')
    def _compute_ocupacion(self):
        for propiedad in self:
            alquiladas = propiedad.unidad_ids.filtered(lambda u: u.estado == 'alquilada')
            propiedad.unidades_total = len(propiedad.unidad_ids)
            propiedad.unidades_alquiladas = len(alquiladas)
            total = len(propiedad.unidad_ids)
            propiedad.ocupacion = f'{len(alquiladas)} de {total} ' + ('alquilada' if total == 1 else 'alquiladas')
            propiedad.alquiler_mensual = sum(alquiladas.contrato_id.mapped('monto'))

    def _compute_deuda(self):
        Cuota = self.env['alquiler.cuota']
        deudas = dict(Cuota._read_group(
            [('propiedad_id', 'in', self._origin.ids)] + Cuota._dominio_vencidas(), ['propiedad_id'], ['saldo:sum']))
        for propiedad in self:
            propiedad.deuda = deudas.get(propiedad._origin, 0)


class AlquilerUnidad(models.Model):
    """Lo que se alquila: una casa entera o un departamento de un edificio."""
    _name = 'alquiler.unidad'
    _description = 'Unidad en alquiler'
    _order = 'propiedad_id, piso, name, id'
    _rec_names_search = ['name', 'propiedad_id.name']

    name = fields.Char('Nombre', required=True, help='Por ejemplo: Casa, Depto 1.')
    propiedad_id = fields.Many2one('alquiler.propiedad', string='Propiedad', required=True, ondelete='cascade',
                                   index=True)
    ciudad = fields.Char(related='propiedad_id.ciudad', store=True)
    company_id = fields.Many2one(related='propiedad_id.company_id', store=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    piso = fields.Integer('Piso')
    descripcion = fields.Char('Descripción', help='Ambientes, comodidades...')
    alquiler_sugerido = fields.Monetary('Alquiler de referencia', help='Se propone al hacer un contrato nuevo.')
    active = fields.Boolean('Activa', default=True)
    # Para la página "Se alquila"
    foto = fields.Image('Foto', max_width=1280, max_height=1280)
    dormitorios = fields.Integer('Dormitorios')
    banos = fields.Integer('Baños')
    detalle_web = fields.Text('Descripción para la página',
                              help='Lo que leen los interesados: comodidades, cercanía, qué incluye.')
    publicar = fields.Boolean('Mostrar en la página "Se alquila"', default=True,
                              help='Mientras esté libre, aparece en la página pública con su foto y su precio.')
    interesado_ids = fields.One2many('alquiler.interesado', 'unidad_id', string='Interesados')
    contrato_ids = fields.One2many('alquiler.contrato', 'unidad_id', string='Contratos')
    contrato_count = fields.Integer('Cantidad de contratos', compute='_compute_contrato_count')
    contrato_id = fields.Many2one('alquiler.contrato', string='Contrato vigente', compute='_compute_contrato',
                                  store=True)
    estado = fields.Selection(ESTADOS_UNIDAD, string='Estado', compute='_compute_contrato', store=True)
    inquilino_id = fields.Many2one(related='contrato_id.inquilino_id', string='Inquilino')
    telefono = fields.Char(related='contrato_id.telefono')
    monto = fields.Monetary(related='contrato_id.monto', string='Alquiler')
    dia_pago = fields.Integer(related='contrato_id.dia_pago')
    deuda = fields.Monetary(related='contrato_id.deuda')
    proximo_vencimiento = fields.Date(related='contrato_id.proximo_vencimiento')
    color = fields.Integer('Color', compute='_compute_situacion')
    situacion = fields.Char('Situación', compute='_compute_situacion')

    @api.depends('name', 'propiedad_id.name', 'propiedad_id.unidad_ids')
    def _compute_display_name(self):
        # "Casa Caacupé" para una casa; "Edificio Ypacaraí · Depto 1" para un departamento.
        for unidad in self:
            propiedad = unidad.propiedad_id
            if propiedad and len(propiedad.unidad_ids) == 1:
                unidad.display_name = propiedad.name
            else:
                unidad.display_name = ' · '.join(parte for parte in (propiedad.name, unidad.name) if parte)

    @api.depends('contrato_ids.estado')
    def _compute_contrato(self):
        for unidad in self:
            vigente = unidad.contrato_ids.filtered(lambda c: c.estado == 'vigente')[:1]
            unidad.contrato_id = vigente
            unidad.estado = 'alquilada' if vigente else 'libre'

    def _compute_contrato_count(self):
        for unidad in self:
            unidad.contrato_count = len(unidad.contrato_ids)

    @api.depends('contrato_id')
    def _compute_situacion(self):
        hoy = fields.Date.context_today(self)
        for unidad in self:
            contrato = unidad.contrato_id
            vence = contrato.proximo_vencimiento
            if not contrato:
                unidad.color, unidad.situacion = COLOR_LIBRE, 'Libre'
            elif contrato.deuda:
                unidad.color, unidad.situacion = COLOR_CON_DEUDA, f'Debe {guaranies(contrato.deuda)}'
            elif vence and (vence - hoy).days <= DIAS_POR_VENCER:
                dias = (vence - hoy).days
                unidad.color = COLOR_POR_VENCER
                unidad.situacion = 'Vence hoy' if dias == 0 else 'Vence mañana' if dias == 1 else f'Vence en {dias} días'
            else:
                unidad.color, unidad.situacion = COLOR_AL_DIA, 'Al día'

    def action_abrir(self):
        """Al tocar una unidad en el tablero: su contrato vigente o, si está libre, la unidad."""
        self.ensure_one()
        if self.contrato_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'alquiler.contrato',
                'res_id': self.contrato_id.id,
                'view_mode': 'form',
                'views': [(False, 'form')],
            }
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'alquiler.unidad',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
        }

    def action_nuevo_contrato(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Nuevo contrato',
            'res_model': 'alquiler.contrato',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'context': {'default_unidad_id': self.id, 'default_monto': self.alquiler_sugerido},
        }

    @api.model
    def action_ver_pagina(self):
        """Abre la página pública "Se alquila" (su dirección se cambia en el parámetro alquileres.url_pagina)."""
        url = self.env['ir.config_parameter'].sudo().get_param(
            'alquileres.url_pagina', 'http://se-alquila.localhost:8072/se-alquila')
        return {'type': 'ir.actions.act_url', 'url': url, 'target': 'new'}

    def action_ver_contratos(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('alquileres.action_alquiler_contrato')
        action['domain'] = [('unidad_id', '=', self.id)]
        action['context'] = {'default_unidad_id': self.id, 'default_monto': self.alquiler_sugerido}
        return action
