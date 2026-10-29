# -*- coding: utf-8 -*-
import re
from collections import defaultdict
from datetime import timedelta
from urllib.parse import quote

import pytz

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import format_datetime

ESTADOS_CITA = [
    ('agendada', 'Agendada'),
    ('confirmada', 'Confirmada'),
    ('en_atencion', 'En atención'),
    ('cobrada', 'Cobrada'),
    ('no_asistio', 'No asistió'),
    ('cancelada', 'Cancelada'),
]
# Citas que todavía se pueden atender y cobrar.
ESTADOS_ABIERTOS = ('agendada', 'confirmada', 'en_atencion')
# Si el cliente no vino o canceló, el horario del estilista queda libre.
ESTADOS_LIBRES = ('no_asistio', 'cancelada')

# Duración de una cita a la que todavía no se le cargaron servicios.
MINUTOS_SIN_SERVICIOS = 30

CANALES_RECORDATORIO = [
    ('correo', 'Correo'),
    ('whatsapp', 'WhatsApp'),
]

ORIGENES_CITA = [
    ('recepcion', 'Recepción'),
    ('internet', 'Internet'),
]


def numero_whatsapp(telefono, codigo_pais='595'):
    """Número en el formato que pide wa.me: solo dígitos, con el código del país y sin el 0 de adelante.
    0981 234 567 → 595981234567; +54 9 11 1234-5678 → 5491112345678."""
    if not telefono:
        return ''
    digitos = re.sub(r'\D', '', telefono)
    if telefono.strip().startswith(('+', '00')):
        return digitos.lstrip('0')
    if digitos.startswith('0'):
        return codigo_pais + digitos[1:]
    if digitos.startswith(codigo_pais):
        return digitos
    return codigo_pais + digitos if digitos else ''


class BellaCita(models.Model):
    _name = 'bella.cita'
    _description = 'Cita'
    _inherit = ['bella.cobro.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'fecha_inicio desc, id desc'
    _check_company_auto = True

    name = fields.Char('Número', readonly=True, copy=False, default='Nuevo')
    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                 default=lambda self: self.env.company)
    cliente_id = fields.Many2one('res.partner', string='Cliente', required=True, tracking=True, index=True,
                                 check_company=True)
    telefono = fields.Char(related='cliente_id.phone', string='Teléfono')
    cliente_email = fields.Char(related='cliente_id.email', string='Correo')
    estilista_id = fields.Many2one('hr.employee', string='Estilista', required=True, tracking=True, index=True,
                                   check_company=True, domain=[('bella_estilista', '=', True)])
    fecha_inicio = fields.Datetime('Inicio', required=True, tracking=True,
                                   default=lambda self: self._default_fecha_inicio())
    duracion = fields.Integer('Duración (min)', compute='_compute_duracion', store=True, precompute=True)
    fecha_fin = fields.Datetime('Fin', required=True, compute='_compute_fecha_fin', store=True, readonly=False,
                                precompute=True)
    estado = fields.Selection(ESTADOS_CITA, string='Estado', default='agendada', required=True, tracking=True,
                              copy=False, group_expand='_group_expand_estados')
    servicio_ids = fields.One2many('bella.cita.servicio', 'cita_id', string='Servicios', copy=True)
    producto_ids = fields.One2many('bella.cita.producto', 'cita_id', string='Productos vendidos', copy=True)
    servicios_texto = fields.Char('Servicios pedidos', compute='_compute_servicios_texto')
    turno_texto = fields.Char('Turno', compute='_compute_turno_texto')
    horario_texto = fields.Char('Horario', compute='_compute_horario_texto')
    dia_texto = fields.Char('Día', compute='_compute_turno_texto')
    nota = fields.Text('Notas')
    recordatorio_enviado = fields.Boolean('Recordatorio enviado', readonly=True, copy=False)
    recordatorio_canal = fields.Selection(CANALES_RECORDATORIO, string='Recordatorio por', readonly=True, copy=False)
    whatsapp_url = fields.Char('Enlace de WhatsApp', compute='_compute_whatsapp_url')
    origen = fields.Selection(ORIGENES_CITA, string='Pedida por', default='recepcion', required=True, readonly=True,
                              copy=False, help='Internet: la clienta reservó sola desde la página de turnos.')

    # Ficha técnica: lo que se le hace en esta cita y lo que se le hizo antes.
    ficha_ids = fields.One2many('bella.ficha.tecnica', 'cita_id', string='Ficha técnica', copy=False)
    ficha_anterior_ids = fields.Many2many('bella.ficha.tecnica', string='Trabajos anteriores',
                                          compute='_compute_ficha_anterior_ids')
    cliente_alergias = fields.Text(related='cliente_id.bella_alergias', string='Alergias')
    cliente_puntos = fields.Integer(related='cliente_id.bella_puntos', string='Puntos de la clienta')
    puntos_activo = fields.Boolean(related='company_id.bella_puntos_activo')
    cliente_tipo_cabello = fields.Char(related='cliente_id.bella_tipo_cabello', string='Tipo de cabello',
                                       readonly=False)

    currency_id = fields.Many2one(related='company_id.currency_id')
    total_servicios = fields.Monetary('Total servicios', compute='_compute_totales', store=True)
    total_productos = fields.Monetary('Total productos', compute='_compute_totales', store=True)
    total = fields.Monetary('Total', compute='_compute_totales', store=True, tracking=True)

    @api.model
    def _default_fecha_inicio(self):
        # La próxima hora en punto.
        return fields.Datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    def _group_expand_estados(self, estados, domain):
        # El kanban muestra siempre el recorrido de la cita; las canceladas y ausentes, solo si hay.
        return ['agendada', 'confirmada', 'en_atencion', 'cobrada']

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code('bella.cita') or 'Nuevo'
        return super().create(vals_list)

    def write(self, vals):
        if 'estado' in vals:
            self._verificar_cambio_estado(vals['estado'])
        if 'fecha_inicio' in vals or 'estilista_id' in vals:
            # Si se cambia el turno, el cliente tiene que recibir el recordatorio del nuevo horario.
            vals = dict(vals, recordatorio_enviado=False, recordatorio_canal=False)
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_excepto_cobradas(self):
        if any(cita.estado == 'cobrada' for cita in self):
            raise UserError('No se puede eliminar una cita cobrada: tiene una factura emitida.')

    # Campos calculados

    @api.depends('servicio_ids.duracion')
    def _compute_duracion(self):
        for cita in self:
            cita.duracion = sum(cita.servicio_ids.mapped('duracion'))

    @api.depends('fecha_inicio', 'duracion')
    def _compute_fecha_fin(self):
        # Sale de los servicios; se puede ajustar a mano o estirando la cita en el calendario.
        for cita in self:
            if cita.fecha_inicio:
                cita.fecha_fin = cita.fecha_inicio + timedelta(minutes=cita.duracion or MINUTOS_SIN_SERVICIOS)

    @api.depends('servicio_ids.servicio_id')
    def _compute_servicios_texto(self):
        for cita in self:
            cita.servicios_texto = ' + '.join(cita.servicio_ids.servicio_id.mapped('name'))

    @api.depends('fecha_inicio', 'estilista_id')
    @api.depends_context('lang')
    def _compute_turno_texto(self):
        for cita in self:
            cita.turno_texto = cita._formato_local(cita.fecha_inicio, "EEEE d 'de' MMMM 'a las' HH:mm")
            cita.dia_texto = cita._formato_local(cita.fecha_inicio, 'EEE d/M')

    @api.depends('fecha_inicio', 'fecha_fin', 'estilista_id')
    def _compute_horario_texto(self):
        for cita in self:
            if cita.fecha_inicio and cita.fecha_fin:
                cita.horario_texto = (f'{cita._formato_local(cita.fecha_inicio, "HH:mm")} a '
                                      f'{cita._formato_local(cita.fecha_fin, "HH:mm")}')
            else:
                cita.horario_texto = False

    @api.depends('cliente_id.mobile', 'cliente_id.phone', 'cliente_id.name', 'company_id', 'fecha_inicio',
                 'estilista_id', 'servicio_ids.servicio_id')
    @api.depends_context('lang')
    def _compute_whatsapp_url(self):
        for cita in self:
            codigo_pais = str(cita.company_id.country_id.phone_code or 595)
            numero = numero_whatsapp(cita.cliente_id.mobile or cita.cliente_id.phone, codigo_pais)
            cita.whatsapp_url = f'https://wa.me/{numero}?text={quote(cita._texto_whatsapp())}' if numero else False

    def _texto_whatsapp(self):
        self.ensure_one()
        servicios = f' ({self.servicios_texto})' if self.servicios_texto else ''
        return (f'¡Hola {self.cliente_id.name}! Te recordamos tu turno en {self.company_id.name}: '
                f'{self.turno_texto}{servicios}, con {self.estilista_id.name}. '
                'Si no podés venir, avisanos por acá, así le damos el lugar a otra persona. ¡Te esperamos!')

    @api.depends('cliente_id', 'ficha_ids')
    def _compute_ficha_anterior_ids(self):
        for cita in self:
            # _origin: en la pantalla, la cita y sus fichas nuevas todavía no tienen id.
            cita.ficha_anterior_ids = self.env['bella.ficha.tecnica'].search([
                ('cliente_id', '=', cita.cliente_id._origin.id),
                ('id', 'not in', cita.ficha_ids._origin.ids),
            ]) if cita.cliente_id else False

    @api.depends('cliente_id.name', 'servicio_ids.servicio_id')
    def _compute_display_name(self):
        # Cliente y servicios: es lo que se lee en el calendario.
        for cita in self:
            partes = [cita.cliente_id.name or cita.name, cita.servicios_texto]
            cita.display_name = ' · '.join(parte for parte in partes if parte)

    @api.depends('servicio_ids.precio', 'producto_ids.subtotal')
    def _compute_totales(self):
        for cita in self:
            cita.total_servicios = sum(cita.servicio_ids.mapped('precio'))
            cita.total_productos = sum(cita.producto_ids.mapped('subtotal'))
            cita.total = cita.total_servicios + cita.total_productos

    def _zona_horaria(self):
        """Zona horaria del estilista (la de su horario de trabajo), para mostrar y comparar horas locales."""
        self.ensure_one()
        return self.estilista_id.sudo().tz or self.env.user.tz or 'UTC'

    def _formato_local(self, momento, formato):
        self.ensure_one()
        if not momento:
            return False
        return format_datetime(self.env, momento, tz=self._zona_horaria(), dt_format=formato)

    def _dia_local(self, momento):
        self.ensure_one()
        return pytz.utc.localize(momento).astimezone(pytz.timezone(self._zona_horaria())).date()

    # Restricciones

    @api.constrains('fecha_inicio', 'fecha_fin')
    def _check_fechas(self):
        for cita in self:
            if cita.fecha_fin <= cita.fecha_inicio:
                raise ValidationError('La cita tiene que terminar después de empezar.')

    @api.constrains('estilista_id', 'fecha_inicio', 'fecha_fin', 'estado')
    def _check_superposicion(self):
        for cita in self.filtered(lambda c: c.estado not in ESTADOS_LIBRES):
            otra = self.search([
                ('id', '!=', cita.id),
                ('estilista_id', '=', cita.estilista_id.id),
                ('estado', 'not in', ESTADOS_LIBRES),
                ('fecha_inicio', '<', cita.fecha_fin),
                ('fecha_fin', '>', cita.fecha_inicio),
            ], limit=1)
            if otra:
                raise ValidationError(
                    f'{cita.estilista_id.name} ya tiene la cita {otra.name} ({otra.cliente_id.name}) '
                    f'de {otra._formato_local(otra.fecha_inicio, "HH:mm")} '
                    f'a {otra._formato_local(otra.fecha_fin, "HH:mm")}. Elija otro horario u otro estilista.')

    @api.constrains('estilista_id', 'fecha_inicio', 'fecha_fin')
    def _check_horario(self):
        """El estilista tiene que estar trabajando: dentro de su horario y sin feriados ni ausencias cargadas."""
        for cita in self.filtered(lambda c: c.estado in ESTADOS_ABIERTOS):
            estilista = cita.estilista_id.sudo()
            horario = estilista.resource_calendar_id
            if not horario:
                continue  # Horario flexible: atiende cuando se le agenda.
            inicio = pytz.utc.localize(cita.fecha_inicio)
            fin = pytz.utc.localize(cita.fecha_fin)
            recurso = estilista.resource_id
            intervalos = horario._work_intervals_batch(inicio, fin, resources=recurso)[recurso.id]
            trabajado = sum((hasta - desde).total_seconds() for desde, hasta, _registros in intervalos)
            if trabajado < (fin - inicio).total_seconds():
                raise ValidationError(
                    f'{estilista.name} no trabaja el {cita._formato_local(cita.fecha_inicio, "EEEE d/M")} '
                    f'de {cita._formato_local(cita.fecha_inicio, "HH:mm")} '
                    f'a {cita._formato_local(cita.fecha_fin, "HH:mm")}. Revise su horario: {horario.name}.')

    @api.constrains('estilista_id', 'servicio_ids')
    def _check_servicios_del_estilista(self):
        for cita in self:
            habilitados = cita.estilista_id.sudo().bella_servicio_ids
            otros = cita.servicio_ids.servicio_id - habilitados if habilitados else False
            if otros:
                raise ValidationError(f'{cita.estilista_id.name} no hace: {", ".join(otros.mapped("name"))}. '
                                      'Elija otro estilista o cambie el servicio.')

    def _verificar_cambio_estado(self, nuevo):
        for cita in self.filtered(lambda c: c.estado != nuevo):
            if cita.estado == 'cobrada':
                raise UserError(f'La cita {cita.name} ya está cobrada; no se puede cambiar de estado.')
            if nuevo == 'cobrada' and not self.env.context.get('bella_cobrando'):
                raise UserError('Para cobrar una cita use el botón "Cobrar": así se emite la factura.')

    # Cobro (ver bella.cobro.mixin)

    def _bella_cobrar(self, metodo_pago, diario=None, fecha=None, puntos=0):
        if self.estado not in ESTADOS_ABIERTOS:
            raise UserError(f'La cita {self.name} no se puede cobrar: está "{self._estado_texto()}".')
        if not self.servicio_ids and not self.producto_ids:
            raise UserError('Cargue los servicios realizados antes de cobrar la cita.')
        factura = super()._bella_cobrar(metodo_pago, diario=diario, fecha=fecha, puntos=puntos)
        self.with_context(bella_cobrando=True).estado = 'cobrada'
        return factura

    def _bella_lineas_factura(self):
        self.ensure_one()
        lineas = [Command.create({
            'display_type': 'line_section',
            'name': f'Cita {self.name} · {self.turno_texto} · Atendió: {self.estilista_id.name}',
        })]
        lineas += [Command.create({
            'product_id': linea.servicio_id.id,
            'quantity': 1,
            'price_unit': linea.precio,
        }) for linea in self.servicio_ids]
        lineas += [Command.create(linea._bella_valores_linea_factura()) for linea in self.producto_ids]
        return lineas

    def _bella_productos_vendidos(self):
        return self.producto_ids

    def _bella_insumos(self):
        insumos = defaultdict(float)
        for linea in self.servicio_ids:
            for insumo in linea.servicio_id.bella_insumo_ids:
                insumos[insumo.producto_id] += insumo.cantidad
        return insumos

    def _estado_texto(self):
        return dict(ESTADOS_CITA)[self.estado]

    # Recordatorios

    def _enviar_recordatorio(self):
        plantilla = self.env.ref('studio_bella.mail_template_recordatorio_cita')
        for cita in self:
            cita.message_post_with_source(plantilla, subtype_xmlid='mail.mt_comment')
        self.write({'recordatorio_enviado': True, 'recordatorio_canal': 'correo'})

    @api.model
    def _cron_enviar_recordatorios(self):
        """Todos los días: avisa por correo a los clientes que tienen cita mañana."""
        ahora = fields.Datetime.now()
        citas = self.search([
            ('estado', 'in', ('agendada', 'confirmada')),
            ('recordatorio_enviado', '=', False),
            ('cliente_id.email', '!=', False),
            ('fecha_inicio', '>', ahora),
            ('fecha_inicio', '<', ahora + timedelta(days=2)),
        ])
        manana = citas.filtered(
            lambda cita: cita._dia_local(cita.fecha_inicio) == cita._dia_local(ahora) + timedelta(days=1))
        manana._enviar_recordatorio()

    # Botones

    def _verificar_estado(self, permitidos, accion):
        for cita in self:
            if cita.estado not in permitidos:
                raise UserError(f'No se puede {accion} la cita {cita.name}: está "{cita._estado_texto()}".')

    def action_confirmar(self):
        self._verificar_estado(('agendada',), 'confirmar')
        self.estado = 'confirmada'
        return True

    def action_iniciar(self):
        self._verificar_estado(('agendada', 'confirmada'), 'empezar a atender')
        self.estado = 'en_atencion'
        return True

    def action_cobrar(self):
        self.ensure_one()
        self._verificar_estado(ESTADOS_ABIERTOS, 'cobrar')
        return {
            'type': 'ir.actions.act_window',
            'name': f'Cobrar {self.name}',
            'res_model': 'bella.cobro.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_cita_id': self.id},
        }

    def action_no_asistio(self):
        self._verificar_estado(('agendada', 'confirmada'), 'marcar como ausente')
        self.estado = 'no_asistio'
        return True

    def action_cancelar(self):
        self._verificar_estado(ESTADOS_ABIERTOS, 'cancelar')
        self.estado = 'cancelada'
        return True

    def action_reagendar(self):
        self._verificar_estado(ESTADOS_LIBRES, 'volver a agendar')
        self.estado = 'agendada'
        return True

    def action_enviar_recordatorio(self):
        self._verificar_estado(('agendada', 'confirmada'), 'enviar el recordatorio de')
        sin_correo = self.cliente_id.filtered(lambda cliente: not cliente.email)
        if sin_correo:
            raise UserError(f'{", ".join(sin_correo.mapped("name"))} no tiene correo cargado.')
        self._enviar_recordatorio()
        return True

    def action_whatsapp(self):
        """Abre WhatsApp (web o la aplicación) con el recordatorio escrito; solo falta tocar Enviar.
        Es gratis y no necesita la API de WhatsApp Business."""
        self.ensure_one()
        self._verificar_estado(('agendada', 'confirmada'), 'enviar el recordatorio de')
        if not self.whatsapp_url:
            raise UserError(f'{self.cliente_id.name} no tiene teléfono cargado.')
        url = self.whatsapp_url
        self.write({'recordatorio_enviado': True, 'recordatorio_canal': 'whatsapp'})
        self.message_post(body=f'Recordatorio por WhatsApp al {self.cliente_id.mobile or self.cliente_id.phone}.')
        return {'type': 'ir.actions.act_url', 'url': url, 'target': 'new'}


class BellaCitaServicio(models.Model):
    _name = 'bella.cita.servicio'
    _description = 'Servicio de la cita'
    _order = 'cita_id, sequence, id'
    _check_company_auto = True

    cita_id = fields.Many2one('bella.cita', string='Cita', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(related='cita_id.company_id', store=True)
    servicio_id = fields.Many2one('product.product', string='Servicio', required=True, check_company=True,
                                  domain=lambda self: self._domain_servicios())
    duracion = fields.Integer('Duración (min)', compute='_compute_duracion', store=True, readonly=False,
                              precompute=True)
    currency_id = fields.Many2one(related='cita_id.currency_id')
    precio = fields.Monetary('Precio', compute='_compute_precio', store=True, readonly=False, precompute=True)

    # Guardados en la línea para el reporte de servicios realizados.
    categoria_id = fields.Many2one(related='servicio_id.categ_id', store=True, string='Categoría')
    estilista_id = fields.Many2one(related='cita_id.estilista_id', store=True, string='Estilista')
    cliente_id = fields.Many2one(related='cita_id.cliente_id', store=True, string='Cliente')
    fecha = fields.Datetime(related='cita_id.fecha_inicio', store=True, string='Fecha')
    estado = fields.Selection(related='cita_id.estado', store=True, string='Estado de la cita')
    liquidacion_id = fields.Many2one('bella.liquidacion.comision', string='Liquidación de comisiones',
                                     readonly=True, copy=False, index=True, ondelete='set null')

    _sql_constraints = [
        ('duracion_positiva', 'CHECK(duracion >= 0)', 'La duración no puede ser negativa.'),
    ]

    @api.model
    def _domain_servicios(self):
        domain = [('type', '=', 'service')]
        categoria = self.env.ref('studio_bella.categoria_servicios', raise_if_not_found=False)
        return domain + [('categ_id', 'child_of', categoria.id)] if categoria else domain

    @api.depends('servicio_id')
    def _compute_duracion(self):
        for linea in self:
            linea.duracion = linea.servicio_id.bella_duracion

    @api.depends('servicio_id')
    def _compute_precio(self):
        for linea in self:
            linea.precio = linea.servicio_id.lst_price


class BellaCitaProducto(models.Model):
    _name = 'bella.cita.producto'
    _inherit = 'bella.linea.producto'
    _description = 'Producto vendido en la cita'
    _order = 'cita_id, sequence, id'
    _check_company_auto = True

    cita_id = fields.Many2one('bella.cita', string='Cita', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='cita_id.company_id', store=True)
    currency_id = fields.Many2one(related='cita_id.currency_id')
    liquidacion_id = fields.Many2one('bella.liquidacion.comision', string='Liquidación de comisiones',
                                     readonly=True, copy=False, index=True, ondelete='set null')
