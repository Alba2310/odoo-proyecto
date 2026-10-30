# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .utiles import enlace_whatsapp, fecha_con_dia, fecha_corta, primer_nombre

ESTADOS_DOSIS = [
    ('al_dia', 'Al día'),
    ('por_vencer', 'Por vencer'),
    ('vencida', 'Vencida'),
    ('renovada', 'Ya se aplicó la siguiente'),
    ('sin_refuerzo', 'No se repite'),
]
# El aviso por WhatsApp junta todas las dosis del dueño que vencen en este tiempo (o que ya vencieron).
DIAS_AVISO_JUNTO = 30


class VetAplicacion(models.Model):
    """Una vacuna o desparasitación aplicada: es una línea del carnet de la mascota y dice cuándo le toca la
    próxima dosis."""
    _name = 'vet.aplicacion'
    _description = 'Vacuna o desparasitación'
    _order = 'fecha desc, id desc'
    _check_company_auto = True

    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                 default=lambda self: self.env.company)
    mascota_id = fields.Many2one('vet.mascota', string='Mascota', required=True, ondelete='cascade', index=True,
                                 check_company=True)
    mascota_emoji = fields.Char(related='mascota_id.emoji')
    especie_id = fields.Many2one(related='mascota_id.especie_id', string='Especie')
    dueno_id = fields.Many2one(related='mascota_id.dueno_id', store=True, string='Dueño', index=True)
    dueno_telefono = fields.Char(related='mascota_id.dueno_telefono', string='Teléfono')
    producto_id = fields.Many2one('product.product', string='Vacuna o antiparasitario', required=True,
                                  check_company=True, domain=[('vet_aplicacion', '!=', False)])
    tipo = fields.Selection(related='producto_id.vet_aplicacion', store=True, string='Tipo')
    fecha = fields.Date('Aplicada el', required=True, default=fields.Date.context_today)
    proxima_fecha = fields.Date('Próxima dosis', compute='_compute_proxima_fecha', store=True, readonly=False,
                                precompute=True)
    lote = fields.Char('Lote')
    profesional_id = fields.Many2one('hr.employee', string='Aplicó', check_company=True,
                                     domain=[('vet_atiende', 'in', ('consultorio', 'ambas'))])
    atencion_id = fields.Many2one('vet.atencion', string='Atención', ondelete='set null', index='btree_not_null')
    linea_id = fields.Many2one('vet.atencion.linea', string='Línea de la atención', ondelete='cascade',
                               index='btree_not_null')
    observaciones = fields.Char('Observaciones', help='Por ejemplo: la trajo aplicada de otra veterinaria.')
    renovada = fields.Boolean('Renovada', compute='_compute_renovada', store=True,
                              help='Ya se aplicó una dosis más nueva del mismo producto.')
    no_avisar = fields.Boolean('No avisar más', help='Por ejemplo: el dueño se mudó o la vacuna ya no se usa.')
    avisada_el = fields.Date('Avisado el', readonly=True, copy=False)
    estado_dosis = fields.Selection(ESTADOS_DOSIS, string='Estado', compute='_compute_estado_dosis')
    url_reserva = fields.Char('Página de turnos', compute='_compute_url_reserva')

    @api.depends('company_id.vet_url_reserva')
    def _compute_url_reserva(self):
        for aplicacion in self:
            aplicacion.url_reserva = aplicacion.company_id._vet_url_reserva()

    @api.depends('fecha', 'producto_id')
    def _compute_proxima_fecha(self):
        for aplicacion in self:
            dias = aplicacion.producto_id.vet_dias_refuerzo
            aplicacion.proxima_fecha = aplicacion.fecha + timedelta(days=dias) if aplicacion.fecha and dias else False

    @api.depends('mascota_id.aplicacion_ids.fecha', 'mascota_id.aplicacion_ids.producto_id')
    def _compute_renovada(self):
        for aplicacion in self:
            aplicacion.renovada = any(
                otra.producto_id == aplicacion.producto_id
                and (otra.fecha, otra._origin.id or 0) > (aplicacion.fecha, aplicacion._origin.id or 0)
                for otra in aplicacion.mascota_id.aplicacion_ids if otra != aplicacion and otra.fecha)

    @api.depends('proxima_fecha', 'renovada', 'company_id.vet_dias_aviso_vacuna')
    def _compute_estado_dosis(self):
        hoy = fields.Date.context_today(self)
        for aplicacion in self:
            if aplicacion.renovada:
                aplicacion.estado_dosis = 'renovada'
            elif not aplicacion.proxima_fecha:
                aplicacion.estado_dosis = 'sin_refuerzo'
            elif aplicacion.proxima_fecha < hoy:
                aplicacion.estado_dosis = 'vencida'
            elif aplicacion.proxima_fecha <= hoy + timedelta(days=aplicacion.company_id.vet_dias_aviso_vacuna):
                aplicacion.estado_dosis = 'por_vencer'
            else:
                aplicacion.estado_dosis = 'al_dia'

    @api.depends('producto_id', 'mascota_id.name', 'fecha')
    def _compute_display_name(self):
        for aplicacion in self:
            aplicacion.display_name = f'{aplicacion.producto_id.name} · {aplicacion.mascota_id.name}'

    @api.constrains('fecha', 'proxima_fecha')
    def _check_fechas(self):
        for aplicacion in self:
            if aplicacion.proxima_fecha and aplicacion.proxima_fecha <= aplicacion.fecha:
                raise ValidationError('La próxima dosis tiene que ser después de la aplicación.')

    def write(self, vals):
        if 'proxima_fecha' in vals or 'fecha' in vals:
            # Otra fecha: el dueño tiene que recibir el aviso de nuevo.
            vals = dict(vals, avisada_el=False)
        return super().write(vals)

    # Avisos

    def _vet_pendientes_del_dueno(self):
        """Las dosis de todas las mascotas del dueño que vencen pronto o ya vencieron, para un solo mensaje."""
        self.ensure_one()
        hoy = fields.Date.context_today(self)
        return self | self.search([
            ('company_id', '=', self.company_id.id),
            ('dueno_id', '=', self.dueno_id.id),
            ('renovada', '=', False),
            ('no_avisar', '=', False),
            ('proxima_fecha', '!=', False),
            ('proxima_fecha', '<=', hoy + timedelta(days=DIAS_AVISO_JUNTO)),
            ('mascota_id.fallecida', '=', False),
        ], order='proxima_fecha, id')

    def _vet_texto_aviso(self):
        """Mensaje para el dueño con las dosis de ``self`` (todas del mismo dueño)."""
        hoy = fields.Date.context_today(self)
        primera = self[:1]
        renglones = []
        for aplicacion in self.sorted(lambda a: (a.proxima_fecha, a.mascota_id.name)):
            if aplicacion.proxima_fecha < hoy:
                cuando = f'que le tocaba el {fecha_corta(aplicacion.proxima_fecha)} (ya está vencida)'
            elif aplicacion.proxima_fecha == hoy:
                cuando = 'que le toca hoy'
            else:
                cuando = f'el {fecha_con_dia(aplicacion.proxima_fecha)}'
            renglones.append(f'• {aplicacion.mascota_id.name}: {aplicacion.producto_id.name}, {cuando}.')
        return (f'¡Hola {primer_nombre(primera.dueno_id.name)}! Te escribimos de {primera.company_id.name} para '
                'recordarte las próximas dosis:\n' + '\n'.join(renglones) +
                f'\nPodés reservar el turno en {primera.company_id._vet_url_reserva()} o respondernos por acá.')

    def action_avisar_whatsapp(self):
        """Abre WhatsApp con el aviso escrito: todas las dosis pendientes de las mascotas de ese dueño juntas."""
        self.ensure_one()
        if self.renovada or not self.proxima_fecha:
            raise UserError('Esta dosis no tiene una próxima aplicación pendiente.')
        dosis = self._vet_pendientes_del_dueno()
        url = enlace_whatsapp(self.dueno_id, dosis._vet_texto_aviso(), self.company_id)
        if not url:
            raise UserError(f'{self.dueno_id.name} no tiene teléfono cargado.')
        dosis.avisada_el = fields.Date.context_today(self)
        for mascota in dosis.mascota_id:
            productos = ', '.join(dosis.filtered(lambda d: d.mascota_id == mascota).producto_id.mapped('name'))
            mascota.message_post(body=f'Aviso de la próxima dosis por WhatsApp ({productos}).')
        return {'type': 'ir.actions.act_url', 'url': url, 'target': 'new'}

    @api.model
    def _cron_avisos(self):
        """Todos los días: avisa por correo a los dueños que se acerca la próxima dosis."""
        hoy = fields.Date.context_today(self)
        plantilla = self.env.ref('veterinaria.mail_template_aviso_vacuna')
        for company in self.env['res.company'].search([]):
            dosis = self.search([
                ('company_id', '=', company.id),
                ('renovada', '=', False),
                ('no_avisar', '=', False),
                ('avisada_el', '=', False),
                ('proxima_fecha', '>=', hoy),
                ('proxima_fecha', '<=', hoy + timedelta(days=company.vet_dias_aviso_vacuna)),
                ('dueno_id.email', '!=', False),
                ('mascota_id.fallecida', '=', False),
            ])
            for aplicacion in dosis:
                plantilla.send_mail(aplicacion.id)
                aplicacion.mascota_id.message_post(
                    body=f'Aviso de la próxima dosis por correo ({aplicacion.producto_id.name}) a '
                         f'{aplicacion.dueno_id.email}.')
            dosis.avisada_el = hoy
