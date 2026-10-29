# -*- coding: utf-8 -*-
import operator
from urllib.parse import quote

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_amount

from .cita import numero_whatsapp

# Una cita por venir cuenta como "ya tiene turno" mientras no se atendió, canceló ni se marcó que no vino.
ESTADOS_TURNO_PEDIDO = ('agendada', 'confirmada')
# Filtros que se pueden armar sobre "Próximo turno" (además de "está / no está establecido").
COMPARACIONES = {
    '=': operator.eq, '!=': operator.ne, '<': operator.lt, '<=': operator.le, '>': operator.gt, '>=': operator.ge,
}


class ResPartner(models.Model):
    _inherit = 'res.partner'

    bella_cita_ids = fields.One2many('bella.cita', 'cliente_id', string='Citas en Studio Bella',
                                     groups='studio_bella.group_bella_recepcion')
    bella_cita_count = fields.Integer('Citas', compute='_compute_bella_cita_count',
                                      groups='studio_bella.group_bella_recepcion')

    # Ficha técnica
    bella_alergias = fields.Text('Alergias y sensibilidades', groups='studio_bella.group_bella_recepcion',
                                 help='Se muestra en rojo en cada cita de la clienta.')
    bella_tipo_cabello = fields.Char('Tipo de cabello', groups='studio_bella.group_bella_recepcion',
                                     help='Por ejemplo: fino, teñido, 30 % de canas, rulos.')
    bella_ficha_ids = fields.One2many('bella.ficha.tecnica', 'cliente_id', string='Fichas técnicas',
                                      groups='studio_bella.group_bella_recepcion')

    # Programa de puntos
    bella_puntos_ids = fields.One2many('bella.puntos', 'cliente_id', string='Movimientos de puntos',
                                       groups='studio_bella.group_bella_recepcion')
    bella_puntos = fields.Integer('Puntos', compute='_compute_bella_puntos',
                                  groups='studio_bella.group_bella_recepcion')

    # Visitas: solo cuentan las citas cobradas (las ventas de mostrador no son una visita a la estilista).
    bella_ultima_visita = fields.Date('Última visita', compute='_compute_bella_visitas', store=True,
                                      groups='studio_bella.group_bella_recepcion')
    bella_visitas = fields.Integer('Visitas', compute='_compute_bella_visitas', store=True,
                                   groups='studio_bella.group_bella_recepcion')
    # currency_id: la moneda de la compañía, campo que agrega Facturación al contacto.
    bella_total_gastado = fields.Monetary('Gastado en citas', compute='_compute_bella_visitas', store=True,
                                          groups='studio_bella.group_bella_recepcion')
    bella_dias_sin_venir = fields.Integer('Días sin venir', compute='_compute_bella_dias_sin_venir',
                                         groups='studio_bella.group_bella_recepcion')
    bella_proxima_cita = fields.Datetime('Próximo turno', compute='_compute_bella_proxima_cita',
                                         search='_search_bella_proxima_cita',
                                         groups='studio_bella.group_bella_recepcion')
    bella_invitada_el = fields.Date('Invitada a volver el', readonly=True, copy=False,
                                    groups='studio_bella.group_bella_recepcion')
    bella_invitacion_url = fields.Char('Enlace de la invitación', compute='_compute_bella_invitacion_url',
                                       groups='studio_bella.group_bella_recepcion')

    def _compute_bella_cita_count(self):
        cantidades = dict(self.env['bella.cita']._read_group(
            [('cliente_id', 'in', self.ids)], ['cliente_id'], ['__count']))
        for partner in self:
            partner.bella_cita_count = cantidades.get(partner, 0)

    @api.depends('bella_puntos_ids.puntos')
    @api.depends_context('company')
    def _compute_bella_puntos(self):
        for partner in self:
            partner.bella_puntos = partner._bella_saldo_puntos(self.env.company)

    def _bella_saldo_puntos(self, company):
        """Saldo de puntos de la clienta en una compañía: cada compañía tiene su propio programa."""
        self.ensure_one()
        if not self._origin.id:
            return 0
        [(saldo,)] = self.env['bella.puntos'].sudo()._read_group(
            [('cliente_id', '=', self._origin.id), ('company_id', '=', company.id)], [], ['puntos:sum'])
        return saldo or 0

    @api.depends('bella_cita_ids.estado', 'bella_cita_ids.fecha_inicio', 'bella_cita_ids.total')
    def _compute_bella_visitas(self):
        for partner in self:
            cobradas = partner.bella_cita_ids.filtered(lambda cita: cita.estado == 'cobrada')
            ultima = max(cobradas, key=lambda cita: cita.fecha_inicio, default=False)
            partner.bella_ultima_visita = ultima._dia_local(ultima.fecha_inicio) if ultima else False
            partner.bella_visitas = len(cobradas)
            partner.bella_total_gastado = sum(cobradas.mapped('total'))

    @api.depends('bella_ultima_visita')
    def _compute_bella_dias_sin_venir(self):
        hoy = fields.Date.context_today(self)
        for partner in self:
            partner.bella_dias_sin_venir = (hoy - partner.bella_ultima_visita).days if partner.bella_ultima_visita else 0

    def _bella_dominio_turnos_pedidos(self):
        return [('estado', 'in', ESTADOS_TURNO_PEDIDO), ('fecha_inicio', '>=', fields.Datetime.now())]

    @api.depends('bella_cita_ids.estado', 'bella_cita_ids.fecha_inicio')
    def _compute_bella_proxima_cita(self):
        proximas = dict(self.env['bella.cita']._read_group(
            [('cliente_id', 'in', self.ids)] + self._bella_dominio_turnos_pedidos(),
            ['cliente_id'], ['fecha_inicio:min']))
        for partner in self:
            partner.bella_proxima_cita = proximas.get(partner, False)

    def _search_bella_proxima_cita(self, operator, value):
        dominio = self._bella_dominio_turnos_pedidos()
        if value is False and operator in ('=', '!='):
            # "Sin turno pedido" / "con turno pedido".
            con_turno = self.env['bella.cita'].search(dominio).cliente_id
            return [('id', 'not in' if operator == '=' else 'in', con_turno.ids)]
        comparar = COMPARACIONES.get(operator)
        if not comparar:
            raise UserError(f'No se puede buscar el próximo turno con "{operator}".')
        valor = fields.Datetime.to_datetime(value)
        proximas = self.env['bella.cita']._read_group(dominio, ['cliente_id'], ['fecha_inicio:min'])
        return [('id', 'in', [cliente.id for cliente, proxima in proximas if comparar(proxima, valor)])]

    @api.depends('name', 'mobile', 'phone', 'bella_ultima_visita', 'bella_puntos')
    @api.depends_context('company')
    def _compute_bella_invitacion_url(self):
        company = self.env.company
        codigo_pais = str(company.country_id.phone_code or 595)
        for partner in self:
            numero = numero_whatsapp(partner.mobile or partner.phone, codigo_pais)
            texto = quote(partner._bella_texto_invitacion())
            partner.bella_invitacion_url = f'https://wa.me/{numero}?text={texto}' if numero else False

    def _bella_texto_invitacion(self):
        self.ensure_one()
        company = self.env.company
        semanas = self.bella_dias_sin_venir // 7
        tiempo = f'Hace {semanas} semanas que no te vemos' if semanas >= 2 else 'Hace un tiempo que no te vemos'
        texto = (f'¡Hola {self.name}! {tiempo} en {company.name} y te extrañamos. ¿Te reservamos un turno? '
                 f'Podés elegir el día y la hora en {company._bella_url_turnos()} o respondernos por acá.')
        if company.bella_puntos_activo and self.bella_puntos > 0:
            descuento = format_amount(self.env, self.bella_puntos * company.bella_puntos_valor, company.currency_id)
            texto += f' Tenés {self.bella_puntos} puntos para usar: {descuento} de descuento.'
        return texto

    def action_bella_ver_citas(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('studio_bella.action_bella_cita')
        action['domain'] = [('cliente_id', '=', self.id)]
        action['context'] = {'default_cliente_id': self.id}
        action['view_mode'] = 'list,calendar,form'
        action['views'] = [(False, 'list'), (False, 'calendar'), (False, 'form')]
        return action

    def action_bella_ver_puntos(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('studio_bella.action_bella_puntos')
        action['domain'] = [('cliente_id', '=', self.id)]
        action['context'] = {'default_cliente_id': self.id}
        return action

    def action_bella_invitar(self):
        """Abre WhatsApp con la invitación a volver escrita; solo falta tocar Enviar."""
        self.ensure_one()
        if not self.bella_invitacion_url:
            raise UserError(f'{self.name} no tiene teléfono cargado.')
        url = self.bella_invitacion_url
        self.bella_invitada_el = fields.Date.context_today(self)
        self.message_post(body=f'Invitación a volver por WhatsApp al {self.mobile or self.phone}.')
        return {'type': 'ir.actions.act_url', 'url': url, 'target': 'new'}
