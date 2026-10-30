# -*- coding: utf-8 -*-
from datetime import datetime

import pytz

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import format_datetime

from .utiles import DIAS, enlace_whatsapp, fecha_con_dia, fecha_corta, primer_nombre

TIPOS = [
    ('internacion', 'Internación'),
    ('hotel', 'Hotel / guardería'),
]
ESTADOS_ESTADIA = [
    ('reservada', 'Reservada'),
    ('activa', 'Adentro'),
    ('alta', 'Salió, falta cobrar'),
    ('cobrada', 'Cobrada'),
    ('cancelada', 'Cancelada'),
]
# Estadías que ocupan el lugar (ahora o en las fechas reservadas).
OCUPAN = ('reservada', 'activa')
TIPOS_LUGAR = [
    ('internacion', 'Internación'),
    ('hotel', 'Hotel'),
    ('ambos', 'Internación y hotel'),
]
COMIO = [
    ('bien', 'Comió bien'),
    ('poco', 'Comió poco'),
    ('nada', 'No comió'),
]
ANIMO = [
    ('bien', 'Animado'),
    ('decaido', 'Decaído'),
    ('muy_decaido', 'Muy decaído'),
]
# Para comparar períodos de estadías sin fecha de salida.
SIN_FIN = datetime(9999, 12, 31)


class VetLugar(models.Model):
    """Jaula, canil, gatera o box donde se queda la mascota internada u hospedada."""
    _name = 'vet.lugar'
    _description = 'Lugar de internación u hotel'
    _order = 'sequence, name'
    _check_company_auto = True

    name = fields.Char('Lugar', required=True)
    sequence = fields.Integer(default=10)
    tipo = fields.Selection(TIPOS_LUGAR, string='Para', required=True, default='ambos')
    nota = fields.Char('Detalle', help='Por ejemplo: para perros grandes, con calefacción.')
    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                 default=lambda self: self.env.company)
    active = fields.Boolean(default=True)
    estadia_id = fields.Many2one('vet.internacion', string='Adentro ahora', compute='_compute_estadia')
    proxima_reserva_id = fields.Many2one('vet.internacion', string='Próxima reserva', compute='_compute_estadia')
    mascota_emoji = fields.Char(compute='_compute_estadia')
    mascota_nombre = fields.Char('Mascota', compute='_compute_estadia')
    estadia_texto = fields.Char('Hace', compute='_compute_estadia')
    reserva_texto = fields.Char('Reservado', compute='_compute_estadia')
    estado_lugar = fields.Selection([('libre', 'Libre'), ('ocupado', 'Ocupado')], string='Estado',
                                    compute='_compute_estadia')

    def _compute_estadia(self):
        estadias = self.env['vet.internacion'].search([('lugar_id', 'in', self.ids), ('estado', 'in', OCUPAN)],
                                                      order='ingreso')
        for lugar in self:
            propias = estadias.filtered(lambda estadia: estadia.lugar_id == lugar)
            adentro = propias.filtered(lambda estadia: estadia.estado == 'activa')[:1]
            reserva = propias.filtered(lambda estadia: estadia.estado == 'reservada')[:1]
            dias = adentro.dias_hasta_hoy
            lugar.estadia_id = adentro
            lugar.proxima_reserva_id = reserva
            lugar.estado_lugar = 'ocupado' if adentro else 'libre'
            lugar.mascota_emoji = adentro.mascota_emoji
            lugar.mascota_nombre = adentro.mascota_id.name
            lugar.estadia_texto = f'{dias} día{"s" if dias != 1 else ""} adentro' if adentro else False
            lugar.reserva_texto = (
                f'{reserva.mascota_id.name}, desde el {fecha_corta(reserva._dia_local(reserva.ingreso))}'
                if reserva else False)

    def _sirve_para(self, tipo):
        self.ensure_one()
        return self.tipo in (tipo, 'ambos')

    def action_abrir_estadia(self):
        """Desde el mapa de lugares: la estadía de quien está adentro o, si está libre, una nueva en ese lugar."""
        self.ensure_one()
        accion = {'type': 'ir.actions.act_window', 'res_model': 'vet.internacion', 'view_mode': 'form'}
        if self.estadia_id:
            return {**accion, 'res_id': self.estadia_id.id}
        return {**accion, 'name': f'Nueva estadía en {self.name}',
                'context': {'default_lugar_id': self.id,
                            'default_tipo': 'hotel' if self.tipo == 'hotel' else 'internacion'}}


class VetInternacion(models.Model):
    """La mascota se queda en la veterinaria: internada (con controles y medicación) o en el hotel."""
    _name = 'vet.internacion'
    _description = 'Internación u hotel'
    _inherit = ['vet.cobrable', 'mail.thread', 'mail.activity.mixin']
    _order = 'ingreso desc, id desc'
    _check_company_auto = True

    name = fields.Char('Número', readonly=True, copy=False, default='Nuevo')
    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                 default=lambda self: self.env.company)
    tipo = fields.Selection(TIPOS, string='Tipo', required=True, default='internacion', tracking=True)
    estado = fields.Selection(ESTADOS_ESTADIA, string='Estado', required=True, default='activa', tracking=True,
                              copy=False)
    mascota_id = fields.Many2one('vet.mascota', string='Mascota', required=True, tracking=True, index=True,
                                 check_company=True)
    dueno_id = fields.Many2one('res.partner', string='Dueño', compute='_compute_dueno_id', store=True,
                               readonly=False, precompute=True, required=True, index=True, check_company=True)
    dueno_telefono = fields.Char(related='mascota_id.dueno_telefono', string='Teléfono')
    mascota_emoji = fields.Char(related='mascota_id.emoji')
    mascota_foto = fields.Image(related='mascota_id.foto', string='Foto')
    mascota_alertas = fields.Char(related='mascota_id.alertas', string='Cuidado')
    mascota_alergias = fields.Text(related='mascota_id.alergias', string='Alergias')
    lugar_id = fields.Many2one('vet.lugar', string='Lugar', required=True, tracking=True, check_company=True,
                               domain="[('tipo', 'in', (tipo, 'ambos'))]")
    ingreso = fields.Datetime('Ingreso', required=True, default=fields.Datetime.now, tracking=True)
    salida_prevista = fields.Datetime('Salida prevista', tracking=True)
    egreso = fields.Datetime('Salió el', readonly=True, copy=False, tracking=True)
    profesional_id = fields.Many2one('hr.employee', string='Veterinario/a a cargo', check_company=True,
                                     domain=[('vet_atiende', 'in', ('consultorio', 'ambas'))])
    atencion_id = fields.Many2one('vet.atencion', string='Consulta de origen', readonly=True, copy=False)
    motivo = fields.Text('Motivo', help='Diagnóstico o por qué se interna; en el hotel, por ejemplo "vacaciones".')
    plan = fields.Text('Indicaciones y medicación', help='Lo que hay que darle y cada cuánto.')
    alimentacion = fields.Char('Alimentación', compute='_compute_alimentacion', store=True, readonly=False,
                               precompute=True)
    pertenencias = fields.Text('Dejó', help='Lo que trajo el dueño: correa, cama, comida, juguetes...')

    producto_dia_id = fields.Many2one('product.product', string='Se cobra por día', compute='_compute_producto_dia',
                                      store=True, readonly=False, precompute=True, check_company=True,
                                      domain=[('vet_area', '=', 'internacion')])
    currency_id = fields.Many2one(related='company_id.currency_id')
    precio_dia = fields.Monetary('Precio por día', compute='_compute_precio_dia', store=True, readonly=False,
                                 precompute=True)
    dias_hasta_hoy = fields.Integer('Días adentro', compute='_compute_dias_hasta_hoy')
    dias_a_cobrar = fields.Integer('Días a cobrar', compute='_compute_dias_a_cobrar', store=True, readonly=False,
                                   precompute=True, help='Desde el día de ingreso hasta el de salida (mínimo uno). '
                                                         'Se puede corregir antes de cobrar.')
    linea_ids = fields.One2many('vet.internacion.linea', 'internacion_id', string='Medicación y extras',
                                copy=False)
    control_ids = fields.One2many('vet.control', 'internacion_id', string='Controles', copy=False)
    ultimo_control = fields.Datetime('Último control', compute='_compute_ultimo_control')
    total_dias = fields.Monetary('Estadía', compute='_compute_total', store=True)
    total = fields.Monetary('Total', compute='_compute_total', store=True, tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code('vet.internacion') or 'Nuevo'
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('estado') == 'cobrada' and not self.env.context.get('vet_cobrando'):
            raise UserError('Para cobrar use el botón "Cobrar": así se emite la factura.')
        if 'estado' in vals and any(estadia.estado == 'cobrada' for estadia in self):
            raise UserError('Una estadía cobrada no cambia de estado.')
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_excepto_cobradas(self):
        if any(estadia.estado == 'cobrada' for estadia in self):
            raise UserError('No se puede borrar una estadía cobrada: tiene una factura emitida.')

    # Campos calculados

    @api.depends('mascota_id')
    def _compute_dueno_id(self):
        for estadia in self:
            estadia.dueno_id = estadia.mascota_id.dueno_id

    @api.depends('mascota_id')
    def _compute_alimentacion(self):
        for estadia in self:
            estadia.alimentacion = estadia.mascota_id.alimentacion

    @api.depends('tipo', 'company_id')
    def _compute_producto_dia(self):
        for estadia in self:
            company = estadia.company_id or self.env.company
            estadia.producto_dia_id = (company.vet_producto_hotel_id if estadia.tipo == 'hotel'
                                       else company.vet_producto_internacion_id)

    @api.depends('producto_dia_id')
    def _compute_precio_dia(self):
        for estadia in self:
            estadia.precio_dia = estadia.producto_dia_id.lst_price

    def _zona_horaria(self):
        self.ensure_one()
        return pytz.timezone(self.company_id.resource_calendar_id.tz or self.env.user.tz or 'America/Asuncion')

    def _dia_local(self, momento):
        return pytz.utc.localize(momento).astimezone(self._zona_horaria()).date()

    def _dias_entre(self, hasta):
        """Días de estadía: del día de ingreso al de salida, y como mínimo uno (un baño de día cuenta uno)."""
        self.ensure_one()
        if not self.ingreso:
            return 0
        return max((self._dia_local(hasta) - self._dia_local(self.ingreso)).days, 1)

    def _compute_dias_hasta_hoy(self):
        ahora = fields.Datetime.now()
        for estadia in self:
            if estadia.estado in ('reservada', 'cancelada'):
                estadia.dias_hasta_hoy = 0
            else:
                estadia.dias_hasta_hoy = estadia._dias_entre(estadia.egreso or ahora)

    @api.depends('ingreso', 'egreso', 'salida_prevista')
    def _compute_dias_a_cobrar(self):
        for estadia in self:
            hasta = estadia.egreso or estadia.salida_prevista or fields.Datetime.now()
            estadia.dias_a_cobrar = estadia._dias_entre(max(hasta, estadia.ingreso)) if estadia.ingreso else 0

    @api.depends('control_ids.fecha')
    def _compute_ultimo_control(self):
        for estadia in self:
            estadia.ultimo_control = max(estadia.control_ids.mapped('fecha'), default=False)

    @api.depends('dias_a_cobrar', 'precio_dia', 'linea_ids.subtotal')
    def _compute_total(self):
        for estadia in self:
            estadia.total_dias = estadia.dias_a_cobrar * estadia.precio_dia
            estadia.total = estadia.total_dias + sum(estadia.linea_ids.mapped('subtotal'))

    @api.depends('mascota_id.name', 'lugar_id.name')
    def _compute_display_name(self):
        for estadia in self:
            estadia.display_name = f'{estadia.mascota_id.name or estadia.name} · {estadia.lugar_id.name or ""}'

    def _tipo_texto(self):
        return dict(TIPOS)[self.tipo].split(' /')[0]

    # Restricciones

    @api.constrains('ingreso', 'salida_prevista', 'egreso')
    def _check_fechas(self):
        for estadia in self:
            if estadia.salida_prevista and estadia.salida_prevista <= estadia.ingreso:
                raise ValidationError('La salida prevista tiene que ser después del ingreso.')
            if estadia.egreso and estadia.egreso < estadia.ingreso:
                raise ValidationError('La salida no puede ser antes del ingreso.')

    @api.constrains('lugar_id', 'tipo')
    def _check_lugar_tipo(self):
        for estadia in self:
            if not estadia.lugar_id._sirve_para(estadia.tipo):
                raise ValidationError(f'{estadia.lugar_id.name} no es para {estadia._tipo_texto().lower()}.')

    @api.constrains('lugar_id', 'estado', 'ingreso', 'salida_prevista')
    def _check_lugar_libre(self):
        """En un lugar hay una sola mascota: no se pisan las estadías (ni las reservas del hotel)."""
        for estadia in self.filtered(lambda e: e.estado in OCUPAN):
            fin = estadia.salida_prevista or SIN_FIN
            for otra in self.search([('id', '!=', estadia.id), ('lugar_id', '=', estadia.lugar_id.id),
                                     ('estado', 'in', OCUPAN)]):
                if otra.ingreso < fin and estadia.ingreso < (otra.salida_prevista or SIN_FIN):
                    cuando = 'está ahí ahora' if otra.estado == 'activa' else (
                        f'tiene reservado desde el {fecha_corta(otra._dia_local(otra.ingreso))}')
                    raise ValidationError(f'{estadia.lugar_id.name} está ocupado: {otra.mascota_id.name} {cuando}. '
                                          'Elija otro lugar o cambie las fechas.')

    def _verificar_estado(self, permitidos, accion):
        for estadia in self:
            if estadia.estado not in permitidos:
                raise UserError(f'No se puede {accion} {estadia.name} ({estadia.mascota_id.name}): está '
                                f'"{dict(ESTADOS_ESTADIA)[estadia.estado]}".')

    # Cobro (ver vet.cobrable)

    def _vet_cobrar(self, pagos, fecha=None):
        self.ensure_one()
        self._verificar_estado(('alta',), 'cobrar')
        factura = super()._vet_cobrar(pagos, fecha=fecha)
        self.with_context(vet_cobrando=True).estado = 'cobrada'
        return factura

    def _vet_lineas_factura(self):
        self.ensure_one()
        lineas = [Command.create({
            'display_type': 'line_section',
            'name': f'{self._tipo_texto()} de {self.mascota_id.name} · {self.name} · {self.lugar_id.name}',
        })]
        if self.producto_dia_id and self.dias_a_cobrar:
            desde = self._dia_local(self.ingreso)
            hasta = self._dia_local(self.egreso or fields.Datetime.now())
            lineas.append(Command.create({
                'product_id': self.producto_dia_id.id,
                'name': f'{self.producto_dia_id.name}: {self.dias_a_cobrar} día{"s" if self.dias_a_cobrar != 1 else ""}'
                        f' (del {desde.strftime("%d/%m")} al {hasta.strftime("%d/%m")})',
                'quantity': self.dias_a_cobrar,
                'price_unit': self.precio_dia,
            }))
        return lineas + [Command.create(linea._vet_valores_factura()) for linea in self.linea_ids]

    def _vet_lineas_vendidas(self):
        return self.linea_ids

    def _vet_falta_stock_frena(self):
        # Los remedios ya se le dieron: se cobra igual y se avisa si el stock quedó en negativo.
        return False

    # WhatsApp al dueño

    def _texto_whatsapp(self):
        self.ensure_one()
        mascota = self.mascota_id
        hola = f'¡Hola {primer_nombre(self.dueno_id.name)}!'
        if self.estado == 'reservada':
            salida = f' al {fecha_con_dia(self._dia_local(self.salida_prevista))}' if self.salida_prevista else ''
            return (f'{hola} Te confirmamos la reserva de {mascota.name} en el hotel de {self.company_id.name}: del '
                    f'{fecha_con_dia(self._dia_local(self.ingreso))}{salida}. ¡L{mascota._vet_terminacion()[0]} '
                    'esperamos!')
        if self.estado == 'alta':
            return (f'{hola} {mascota.name} ya puede volver a casa: pasá a retirarl{mascota._vet_terminacion()} '
                    'cuando quieras.')
        control = self.control_ids.sorted('fecha', reverse=True)[:1]
        if not control:
            return (f'{hola} {mascota.name} ya está instalad{mascota._vet_terminacion()} en {self.lugar_id.name}. '
                    'Te vamos contando cómo sigue.')
        local = pytz.utc.localize(control.fecha).astimezone(self._zona_horaria())
        cuando = f'{DIAS[local.weekday()]} {local.day} a las {local:%H:%M}'
        partes = [dict(ANIMO)[control.animo].lower() if control.animo else '',
                  dict(COMIO)[control.comio].lower() if control.comio else '',
                  f'temperatura {control.temperatura:.1f} °C'.replace('.', ',') if control.temperatura else '']
        texto = f'{hola} Te contamos cómo está {mascota.name} ({cuando}): ' + ', '.join(p for p in partes if p) + '.'
        if control.medicacion:
            texto += f' Le dimos: {control.medicacion.strip()}.'
        if control.observaciones:
            texto += f' {control.observaciones.strip()}'
        return texto + ' Cualquier novedad te avisamos.'

    def action_whatsapp(self):
        """Según el momento: confirma la reserva, manda el parte del último control o avisa que ya puede salir."""
        self.ensure_one()
        self._verificar_estado(('reservada', 'activa', 'alta'), 'avisar al dueño de')
        url = enlace_whatsapp(self.dueno_id, self._texto_whatsapp(), self.company_id)
        if not url:
            raise UserError(f'{self.dueno_id.name} no tiene teléfono cargado.')
        que = {'reservada': 'Confirmación de la reserva', 'activa': 'Parte del día', 'alta': 'Aviso de retiro'}
        self.message_post(body=f'{que[self.estado]} por WhatsApp al {self.dueno_telefono}.')
        return {'type': 'ir.actions.act_url', 'url': url, 'target': 'new'}

    # Botones

    def action_ingresar(self):
        self._verificar_estado(('reservada',), 'marcar el ingreso de')
        for estadia in self:
            ahora = fields.Datetime.now()
            valores = {'estado': 'activa', 'ingreso': ahora}
            if estadia.salida_prevista and estadia.salida_prevista <= ahora:
                valores['salida_prevista'] = False
            estadia.write(valores)
        return True

    def action_dar_alta(self):
        self._verificar_estado(('activa',), 'dar de alta')
        self.write({'estado': 'alta', 'egreso': fields.Datetime.now()})
        return True

    def action_cobrar(self):
        self.ensure_one()
        self._verificar_estado(('alta',), 'cobrar')
        return self._vet_abrir_cobro('internacion_id')

    def action_cancelar(self):
        self._verificar_estado(('reservada', 'activa'), 'cancelar')
        if self.linea_ids:
            raise UserError('Tiene medicación o extras cargados: déle el alta y cóbrela.')
        self.estado = 'cancelada'
        return True

    def action_nuevo_control(self):
        self.ensure_one()
        self._verificar_estado(('activa',), 'cargar un control de')
        return {
            'type': 'ir.actions.act_window',
            'name': f'Control de {self.mascota_id.name}',
            'res_model': 'vet.control',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_internacion_id': self.id},
        }

    def action_imprimir_ingreso(self):
        return self.env.ref('veterinaria.action_report_ingreso').report_action(self)


class VetInternacionLinea(models.Model):
    _name = 'vet.internacion.linea'
    _inherit = 'vet.linea.venta'
    _description = 'Medicación o extra de la estadía'
    _order = 'internacion_id, fecha, sequence, id'
    _check_company_auto = True

    internacion_id = fields.Many2one('vet.internacion', string='Estadía', required=True, ondelete='cascade',
                                     index=True)
    company_id = fields.Many2one(related='internacion_id.company_id', store=True)
    currency_id = fields.Many2one(related='internacion_id.currency_id')
    fecha = fields.Date('Día', required=True, default=fields.Date.context_today)

    def _vet_documento(self):
        return self.internacion_id


class VetControl(models.Model):
    """Lo que se anota cada vez que se revisa a un internado (u hospedado): signos, si comió, la medicación."""
    _name = 'vet.control'
    _description = 'Control de internación'
    _inherit = 'vet.registra.peso'
    _order = 'fecha desc, id desc'
    _vet_campo_peso = 'control_id'

    internacion_id = fields.Many2one('vet.internacion', string='Estadía', required=True, ondelete='cascade',
                                     index=True)
    mascota_id = fields.Many2one(related='internacion_id.mascota_id', store=True, string='Mascota')
    company_id = fields.Many2one(related='internacion_id.company_id', store=True)
    fecha = fields.Datetime('Cuándo', required=True, default=fields.Datetime.now)
    responsable_id = fields.Many2one('res.users', string='Lo hizo', default=lambda self: self.env.user)
    temperatura = fields.Float('Temperatura (°C)', digits=(4, 1))
    peso = fields.Float('Peso (kg)', digits=(6, 2))
    frecuencia_cardiaca = fields.Integer('Frecuencia cardíaca (lpm)')
    comio = fields.Selection(COMIO, string='Comida')
    animo = fields.Selection(ANIMO, string='Ánimo')
    orino = fields.Boolean('Orinó')
    defeco = fields.Boolean('Defecó')
    medicacion = fields.Text('Medicación dada')
    observaciones = fields.Text('Observaciones')

    @api.constrains('internacion_id')
    def _check_estadia_activa(self):
        for control in self:
            if control.internacion_id.estado != 'activa':
                raise ValidationError('Solo se cargan controles de las mascotas que están adentro.')

    @api.depends('fecha', 'internacion_id')
    def _compute_display_name(self):
        for control in self:
            control.display_name = (f'{control.internacion_id.mascota_id.name}: '
                                    f'{format_datetime(self.env, control.fecha, dt_format="d/M HH:mm")}')

    def _vet_datos_peso(self):
        return {'fecha': self.internacion_id._dia_local(self.fecha),
                'origen': f'Control de {self.internacion_id._tipo_texto().lower()}'}

    def _vet_cambia_fecha_peso(self, vals):
        return 'fecha' in vals
