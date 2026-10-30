# -*- coding: utf-8 -*-
from datetime import timedelta

import pytz

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import format_datetime

from .utiles import enlace_whatsapp, primer_nombre

AREAS_AGENDA = [
    ('consultorio', 'Consultorio'),
    ('estetica', 'Baño y peluquería'),
]

# El recorrido de la mascota dentro de la veterinaria: tiene turno, llega, la atienden, está lista y se cobra.
ESTADOS = [
    ('reservada', 'Turno reservado'),
    ('en_espera', 'En sala de espera'),
    ('en_curso', 'En atención'),
    ('lista', 'Terminada'),
    ('cobrada', 'Cobrada'),
    ('ausente', 'No vino'),
    ('cancelada', 'Cancelada'),
]
ABIERTOS = ('reservada', 'en_espera', 'en_curso', 'lista')
# Las columnas del tablero, en orden: una tarjeta se arrastra hacia adelante o hacia atrás entre ellas.
TABLERO = ABIERTOS
# Si no vino o canceló, el horario del profesional queda libre.
LIBERAN = ('ausente', 'cancelada')

ORIGENES = [
    ('recepcion', 'Turno dado en la veterinaria'),
    ('internet', 'Turno pedido por internet'),
    ('sin_turno', 'Llegó sin turno'),
]

# Lo que ocupa en la agenda un turno al que todavía no se le cargaron servicios.
MINUTOS_MINIMOS = 30

CONDICION_CORPORAL = [
    ('1', '1 · Muy flaco'),
    ('2', '2 · Flaco'),
    ('3', '3 · Ideal'),
    ('4', '4 · Con sobrepeso'),
    ('5', '5 · Obeso'),
]


class VetAtencion(models.Model):
    """Cada vez que una mascota pasa por la veterinaria: al consultorio o a baño y peluquería.

    Empieza como turno de la agenda (o "llegó sin turno"), guarda la historia clínica o lo que se hizo en la
    peluquería, y se cobra con factura.
    """
    _name = 'vet.atencion'
    _description = 'Atención'
    _inherit = ['vet.cobrable', 'vet.registra.peso', 'mail.thread', 'mail.activity.mixin']
    _order = 'fecha_inicio desc, id desc'
    _check_company_auto = True
    _vet_campo_peso = 'atencion_id'

    name = fields.Char('Número', readonly=True, copy=False, default='Nuevo')
    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                 default=lambda self: self.env.company)
    area = fields.Selection(AREAS_AGENDA, string='Área', required=True, default='consultorio', tracking=True)
    origen = fields.Selection(ORIGENES, string='Origen', required=True, default='recepcion', copy=False)
    estado = fields.Selection(ESTADOS, string='Estado', required=True, default='reservada', tracking=True,
                              copy=False, group_expand='_group_expand_estados')

    mascota_id = fields.Many2one('vet.mascota', string='Mascota', required=True, tracking=True, index=True,
                                 check_company=True)
    dueno_id = fields.Many2one('res.partner', string='Dueño', compute='_compute_dueno_id', store=True,
                               readonly=False, precompute=True, required=True, index=True, check_company=True)
    dueno_telefono = fields.Char(related='mascota_id.dueno_telefono', string='Teléfono')
    mascota_foto = fields.Image(related='mascota_id.foto', string='Foto')
    mascota_emoji = fields.Char(related='mascota_id.emoji')
    mascota_alertas = fields.Char(related='mascota_id.alertas', string='Cuidado')
    mascota_alergias = fields.Text(related='mascota_id.alergias', string='Alergias')
    especie_id = fields.Many2one(related='mascota_id.especie_id', string='Especie')
    profesional_id = fields.Many2one('hr.employee', string='Atiende', tracking=True, index=True, check_company=True,
                                     domain="[('vet_atiende', 'in', (area, 'ambas'))]")

    fecha_inicio = fields.Datetime('Turno', required=True, tracking=True,
                                   default=lambda self: self._default_fecha_inicio())
    duracion = fields.Integer('Duración (min)', compute='_compute_duracion', store=True, precompute=True)
    fecha_fin = fields.Datetime('Hasta', required=True, compute='_compute_fecha_fin', store=True, readonly=False,
                                precompute=True)
    llegada = fields.Datetime('Llegó a las', readonly=True, copy=False)
    inicio_atencion = fields.Datetime('La atendieron a las', readonly=True, copy=False)
    fin_atencion = fields.Datetime('Terminó a las', readonly=True, copy=False)
    motivo = fields.Char('Motivo', help='Lo que pidió el dueño al sacar el turno.')

    linea_ids = fields.One2many('vet.atencion.linea', 'atencion_id', string='Servicios y productos', copy=True)
    servicios_texto = fields.Char('Servicios', compute='_compute_servicios_texto')
    aplicacion_ids = fields.One2many('vet.aplicacion', 'atencion_id', string='Vacunas y desparasitaciones')
    currency_id = fields.Many2one(related='company_id.currency_id')
    total = fields.Monetary('Total', compute='_compute_total', store=True, tracking=True)

    # Historia clínica (consultorio)
    anamnesis = fields.Text('Lo que cuenta el dueño')
    peso = fields.Float('Peso (kg)', digits=(6, 2))
    temperatura = fields.Float('Temperatura (°C)', digits=(4, 1))
    frecuencia_cardiaca = fields.Integer('Frecuencia cardíaca (lpm)')
    frecuencia_respiratoria = fields.Integer('Frecuencia respiratoria (rpm)')
    condicion_corporal = fields.Selection(CONDICION_CORPORAL, string='Condición corporal')
    examen = fields.Text('Examen físico')
    diagnostico = fields.Text('Diagnóstico')
    tratamiento = fields.Text('Tratamiento hecho')
    indicaciones = fields.Text('Indicaciones para la casa', help='Se imprimen para el dueño.')
    proximo_control = fields.Date('Próximo control')

    # Baño y peluquería
    estetica_pedido = fields.Text('Qué pidió el dueño', help='Por ejemplo: corte cachorro, dejar las orejas largas.')
    estetica_observaciones = fields.Text('Lo que encontramos',
                                         help='Pulgas, garrapatas, nudos, heridas, uñas largas: se le cuenta al dueño '
                                              'al retirar.')

    # Avisos
    recordatorio_enviado = fields.Boolean('Recordatorio enviado', readonly=True, copy=False)
    aviso_lista_el = fields.Datetime('Avisado que está lista', readonly=True, copy=False)

    # Para la agenda
    turno_texto = fields.Char('Cuándo', compute='_compute_textos')
    hora_texto = fields.Char('Hora', compute='_compute_textos')

    @api.model
    def _default_fecha_inicio(self):
        if self.env.context.get('default_origen') == 'sin_turno':
            return fields.Datetime.now()
        # La próxima hora en punto.
        return fields.Datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    def _group_expand_estados(self, estados, domain):
        return ['reservada', 'en_espera', 'en_curso', 'lista', 'cobrada']

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code('vet.atencion') or 'Nuevo'
            if vals.get('origen') == 'sin_turno':
                vals.setdefault('estado', 'en_espera')
                vals.setdefault('llegada', fields.Datetime.now())
                vals.setdefault('fecha_inicio', fields.Datetime.now())
        return super().create(vals_list)

    def write(self, vals):
        if 'estado' in vals:
            self._verificar_cambio_estado(vals['estado'])
        if {'fecha_inicio', 'profesional_id'} & set(vals):
            # Si cambia el turno, el dueño tiene que recibir el recordatorio del horario nuevo.
            vals = dict(vals, recordatorio_enviado=False)
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_excepto_cobradas(self):
        if any(atencion.estado == 'cobrada' for atencion in self):
            raise UserError('No se puede borrar una atención cobrada: tiene una factura emitida.')

    # Campos calculados

    @api.depends('mascota_id')
    def _compute_dueno_id(self):
        for atencion in self:
            atencion.dueno_id = atencion.mascota_id.dueno_id

    @api.depends('linea_ids.producto_id')
    def _compute_duracion(self):
        for atencion in self:
            atencion.duracion = sum(atencion.linea_ids.producto_id.mapped('vet_duracion'))

    @api.depends('fecha_inicio', 'duracion')
    def _compute_fecha_fin(self):
        # Sale de los servicios; se puede ajustar a mano o estirando el turno en la agenda.
        for atencion in self:
            if atencion.fecha_inicio:
                atencion.fecha_fin = atencion.fecha_inicio + timedelta(minutes=atencion.duracion or MINUTOS_MINIMOS)

    @api.depends('linea_ids.producto_id')
    def _compute_servicios_texto(self):
        for atencion in self:
            atencion.servicios_texto = ' + '.join(atencion.linea_ids.producto_id.mapped('name'))

    @api.depends('linea_ids.subtotal')
    def _compute_total(self):
        for atencion in self:
            atencion.total = sum(atencion.linea_ids.mapped('subtotal'))

    @api.depends('fecha_inicio', 'profesional_id')
    @api.depends_context('lang')
    def _compute_textos(self):
        for atencion in self:
            atencion.turno_texto = atencion._formato_local(atencion.fecha_inicio, "EEEE d 'de' MMMM 'a las' HH:mm")
            atencion.hora_texto = atencion._formato_local(atencion.fecha_inicio, 'HH:mm')

    @api.depends('mascota_id.name', 'servicios_texto')
    def _compute_display_name(self):
        # Mascota y servicios: es lo que se lee en la agenda.
        for atencion in self:
            partes = [atencion.mascota_id.name or atencion.name, atencion.servicios_texto]
            atencion.display_name = ' · '.join(parte for parte in partes if parte)

    def _zona_horaria(self):
        self.ensure_one()
        return (self.profesional_id.sudo().tz or self.company_id.resource_calendar_id.tz or self.env.user.tz
                or 'America/Asuncion')

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
        for atencion in self:
            if atencion.fecha_fin <= atencion.fecha_inicio:
                raise ValidationError('El turno tiene que terminar después de empezar.')

    @api.constrains('profesional_id', 'origen', 'area')
    def _check_profesional(self):
        for atencion in self:
            profesional = atencion.profesional_id.sudo()
            if not profesional:
                if atencion.origen != 'sin_turno':
                    raise ValidationError('Elija quién atiende el turno.')
                continue
            if not profesional._vet_hace(atencion.area):
                raise ValidationError(f'{profesional.name} no atiende en '
                                      f'{dict(AREAS_AGENDA)[atencion.area].lower()}.')

    @api.constrains('profesional_id', 'fecha_inicio', 'fecha_fin', 'estado', 'origen')
    def _check_superposicion(self):
        """Dos turnos del mismo profesional no se pisan. Los que llegan sin turno se atienden en un hueco y no
        ocupan la agenda."""
        for atencion in self.filtered(lambda a: a.origen != 'sin_turno' and a.estado not in LIBERAN
                                      and a.profesional_id):
            otra = self.search([
                ('id', '!=', atencion.id),
                ('profesional_id', '=', atencion.profesional_id.id),
                ('origen', '!=', 'sin_turno'),
                ('estado', 'not in', LIBERAN),
                ('fecha_inicio', '<', atencion.fecha_fin),
                ('fecha_fin', '>', atencion.fecha_inicio),
            ], limit=1)
            if otra:
                raise ValidationError(
                    f'{atencion.profesional_id.name} ya tiene el turno de {otra.mascota_id.name} '
                    f'de {otra._formato_local(otra.fecha_inicio, "HH:mm")} '
                    f'a {otra._formato_local(otra.fecha_fin, "HH:mm")}. Elija otro horario u otra persona.')

    @api.constrains('profesional_id', 'fecha_inicio', 'fecha_fin', 'estado')
    def _check_horario(self):
        """Un turno se da cuando el profesional trabaja: dentro de su horario, sin feriados ni ausencias."""
        if self.env.context.get('vet_sin_horario'):
            return  # Solo para cargar datos de ejemplo.
        for atencion in self.filtered(lambda a: a.estado == 'reservada' and a.origen != 'sin_turno'):
            profesional = atencion.profesional_id.sudo()
            horario = profesional.resource_calendar_id
            if not horario:
                continue  # Sin horario: atiende cuando se le da turno.
            inicio = pytz.utc.localize(atencion.fecha_inicio)
            fin = pytz.utc.localize(atencion.fecha_fin)
            recurso = profesional.resource_id
            intervalos = horario._work_intervals_batch(inicio, fin, resources=recurso)[recurso.id]
            trabajado = sum((hasta - desde).total_seconds() for desde, hasta, _registros in intervalos)
            if trabajado < (fin - inicio).total_seconds():
                raise ValidationError(
                    f'{profesional.name} no trabaja el {atencion._formato_local(atencion.fecha_inicio, "EEEE d/M")} '
                    f'de {atencion._formato_local(atencion.fecha_inicio, "HH:mm")} '
                    f'a {atencion._formato_local(atencion.fecha_fin, "HH:mm")}. Revise su horario: {horario.name}.')

    @api.constrains('profesional_id', 'linea_ids')
    def _check_servicios_del_profesional(self):
        for atencion in self:
            habilitados = atencion.profesional_id.sudo().vet_servicio_ids
            if not habilitados:
                continue
            servicios = atencion.linea_ids.producto_id.filtered(
                lambda producto: producto.vet_area in ('consultorio', 'estetica') and producto.type == 'service')
            otros = servicios - habilitados
            if otros:
                raise ValidationError(f'{atencion.profesional_id.name} no hace: {", ".join(otros.mapped("name"))}. '
                                      'Elija otra persona o cambie el servicio.')

    def _verificar_cambio_estado(self, nuevo):
        for atencion in self.filtered(lambda a: a.estado != nuevo):
            if atencion.estado == 'cobrada':
                raise UserError(f'{atencion.name} ya está cobrada: no se puede cambiar de estado.')
            if nuevo == 'cobrada' and not self.env.context.get('vet_cobrando'):
                raise UserError('Para cobrar use el botón "Cobrar": así se emite la factura.')

    def _verificar_estado(self, permitidos, accion):
        for atencion in self:
            if atencion.estado not in permitidos:
                raise UserError(f'No se puede {accion} {atencion.name} ({atencion.mascota_id.name}): está '
                                f'"{dict(ESTADOS)[atencion.estado]}".')

    # Peso (ver vet.registra.peso)

    def _vet_datos_peso(self):
        return {'fecha': self._dia_local(self.fecha_inicio), 'origen': f'Atención {self.name}'}

    def _vet_cambia_fecha_peso(self, vals):
        return 'fecha_inicio' in vals

    # Vacunas y desparasitaciones

    def _vet_registrar_aplicaciones(self):
        """Lo que se aplicó queda en el carnet de la mascota, con la fecha de la próxima dosis."""
        Aplicacion = self.env['vet.aplicacion']
        for atencion in self:
            dia = atencion._dia_local(atencion.fecha_inicio)
            for linea in atencion.linea_ids.filtered(lambda l: l.producto_id.vet_aplicacion and not l.aplicacion_ids):
                Aplicacion.create({
                    'mascota_id': atencion.mascota_id.id,
                    'producto_id': linea.producto_id.id,
                    'fecha': dia,
                    'lote': linea.lote,
                    'profesional_id': atencion.profesional_id.id,
                    'atencion_id': atencion.id,
                    'linea_id': linea.id,
                    'company_id': atencion.company_id.id,
                })

    # Cobro (ver vet.cobrable)

    def _vet_cobrar(self, pagos, fecha=None):
        self.ensure_one()
        self._verificar_estado(ABIERTOS, 'cobrar')
        if not self.linea_ids:
            raise UserError('Cargue lo que se hizo antes de cobrar.')
        self._vet_registrar_aplicaciones()
        factura = super()._vet_cobrar(pagos, fecha=fecha)
        valores = {'estado': 'cobrada'}
        if not self.fin_atencion:
            valores['fin_atencion'] = fields.Datetime.now()
        self.with_context(vet_cobrando=True).write(valores)
        return factura

    def _vet_lineas_factura(self):
        self.ensure_one()
        quien = f' · Atendió: {self.profesional_id.name}' if self.profesional_id else ''
        lineas = [Command.create({
            'display_type': 'line_section',
            'name': f'{self.mascota_id.name} ({self.especie_id.name}) · {self.name}{quien}',
        })]
        return lineas + [Command.create(linea._vet_valores_factura()) for linea in self.linea_ids]

    def _vet_lineas_vendidas(self):
        return self.linea_ids

    # Recordatorios y avisos por WhatsApp (wa.me: gratis, sale del WhatsApp abierto en la computadora)

    def _texto_recordatorio(self):
        self.ensure_one()
        return (f'¡Hola {primer_nombre(self.dueno_id.name)}! Te recordamos el turno de {self.mascota_id.name} en '
                f'{self.company_id.name}: {self.turno_texto}'
                f'{f" ({self.servicios_texto})" if self.servicios_texto else ""}. '
                'Si no pueden venir, avisanos por acá así le damos el lugar a otra mascota.')

    def _texto_lista(self):
        self.ensure_one()
        mascota = self.mascota_id
        termina = mascota._vet_terminacion()
        if self.area == 'estetica':
            texto = (f'¡Hola {primer_nombre(self.dueno_id.name)}! {mascota.name} ya está list{termina} y '
                     f'perfumad{termina}. Podés pasar a retirarl{termina} cuando quieras.')
        else:
            texto = (f'¡Hola {primer_nombre(self.dueno_id.name)}! Ya terminamos con {mascota.name}: podés pasar a '
                     f'retirarl{termina}.')
        if self.estetica_observaciones and self.area == 'estetica':
            texto += f' Te contamos: {self.estetica_observaciones.strip()}'
        return texto

    def _abrir_whatsapp(self, texto, nota):
        self.ensure_one()
        url = enlace_whatsapp(self.dueno_id, texto, self.company_id)
        if not url:
            raise UserError(f'{self.dueno_id.name} no tiene teléfono cargado.')
        self.message_post(body=f'{nota} por WhatsApp al {self.dueno_telefono}.')
        return {'type': 'ir.actions.act_url', 'url': url, 'target': 'new'}

    def action_recordatorio_whatsapp(self):
        self.ensure_one()
        self._verificar_estado(('reservada',), 'mandar el recordatorio de')
        accion = self._abrir_whatsapp(self._texto_recordatorio(), 'Recordatorio del turno')
        self.recordatorio_enviado = True
        return accion

    def action_avisar_lista(self):
        self.ensure_one()
        self._verificar_estado(('lista',), 'avisar que está lista')
        accion = self._abrir_whatsapp(self._texto_lista(), 'Aviso de que está lista para retirar')
        self.aviso_lista_el = fields.Datetime.now()
        return accion

    @api.model
    def _cron_recordatorios(self):
        """Todos los días: avisa por correo a los dueños que tienen turno mañana."""
        ahora = fields.Datetime.now()
        atenciones = self.search([
            ('estado', '=', 'reservada'),
            ('recordatorio_enviado', '=', False),
            ('dueno_id.email', '!=', False),
            ('fecha_inicio', '>', ahora),
            ('fecha_inicio', '<', ahora + timedelta(days=2)),
        ])
        manana = atenciones.filtered(
            lambda atencion: atencion._dia_local(atencion.fecha_inicio) == atencion._dia_local(ahora) + timedelta(days=1))
        plantilla = self.env.ref('veterinaria.mail_template_recordatorio_turno')
        for atencion in manana:
            atencion.message_post_with_source(plantilla, subtype_xmlid='mail.mt_comment')
        manana.recordatorio_enviado = True

    # Botones del recorrido

    def action_llego(self):
        self._verificar_estado(('reservada',), 'marcar que llegó')
        self.write({'estado': 'en_espera', 'llegada': fields.Datetime.now()})
        return True

    def action_atender(self):
        self._verificar_estado(('reservada', 'en_espera'), 'empezar a atender')
        ahora = fields.Datetime.now()
        for atencion in self:
            valores = {'estado': 'en_curso', 'inicio_atencion': ahora}
            if not atencion.llegada:
                valores['llegada'] = ahora
            if not atencion.profesional_id:
                # Llegó sin turno: la atiende quien aprieta el botón, si es del área.
                empleado = self.env.user.employee_id
                if not empleado or not empleado.sudo()._vet_hace(atencion.area):
                    raise UserError(f'Elija quién atiende a {atencion.mascota_id.name}: abra la atención y complete '
                                    '"Atiende".')
                valores['profesional_id'] = empleado.id
            atencion.write(valores)
        return True

    def action_terminar(self):
        self._verificar_estado(('reservada', 'en_espera', 'en_curso'), 'terminar')
        ahora = fields.Datetime.now()
        for atencion in self:
            atencion.write({
                'estado': 'lista',
                'fin_atencion': ahora,
                'inicio_atencion': atencion.inicio_atencion or ahora,
                'llegada': atencion.llegada or ahora,
            })
        self._vet_registrar_aplicaciones()
        return True

    def action_mover(self, estado):
        """La tarjeta se arrastró a otra columna del tablero. Hacia adelante hace lo mismo que el botón de ese paso;
        hacia atrás deshace (por si se tocó de más): borra las horas que ya no corresponden y, si deja de estar
        terminada, lo que se había anotado en el carnet (se vuelve a anotar al terminar)."""
        self.ensure_one()
        if estado == self.estado:
            return True
        if estado not in TABLERO or self.estado not in TABLERO:
            raise UserError(f'{self.mascota_id.name} no se puede pasar a esa columna: está '
                            f'"{dict(ESTADOS)[self.estado]}".')
        if TABLERO.index(estado) > TABLERO.index(self.estado):
            return {'en_espera': self.action_llego, 'en_curso': self.action_atender,
                    'lista': self.action_terminar}[estado]()
        if estado == 'reservada' and self.origen == 'sin_turno':
            raise UserError(f'{self.mascota_id.name} llegó sin turno: no tiene un turno al que volver.')
        valores = {'estado': estado, 'fin_atencion': False, 'aviso_lista_el': False}
        if estado in ('reservada', 'en_espera'):
            valores['inicio_atencion'] = False
        if estado == 'reservada':
            valores['llegada'] = False
        anterior = dict(ESTADOS)[self.estado]
        if self.estado == 'lista':
            # sudo: el personal no borra vacunas del carnet, pero estas las anotó el sistema al terminar.
            self.aplicacion_ids.filtered('linea_id').sudo().unlink()
        self.write(valores)
        self.message_post(body=f'Se volvió de "{anterior}" a "{dict(ESTADOS)[estado]}" en el tablero.')
        return True

    def action_cobrar(self):
        self.ensure_one()
        self._verificar_estado(ABIERTOS, 'cobrar')
        if not self.linea_ids:
            raise UserError('Cargue lo que se hizo antes de cobrar.')
        return self._vet_abrir_cobro('atencion_id')

    def action_ausente(self):
        self._verificar_estado(('reservada', 'en_espera'), 'marcar que no vino')
        self.estado = 'ausente'
        return True

    def action_cancelar(self):
        self._verificar_estado(('reservada', 'en_espera'), 'cancelar')
        self.estado = 'cancelada'
        return True

    def action_reabrir(self):
        self._verificar_estado(LIBERAN, 'volver a reservar')
        self.estado = 'reservada'
        return True

    def action_internar(self):
        """De la consulta a la internación, con la mascota y el diagnóstico ya cargados."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Internar a {self.mascota_id.name}',
            'res_model': 'vet.internacion',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_tipo': 'internacion',
                'default_mascota_id': self.mascota_id.id,
                'default_profesional_id': self.profesional_id.id,
                'default_motivo': self.diagnostico or self.motivo,
                'default_atencion_id': self.id,
            },
        }

    def action_imprimir_indicaciones(self):
        return self.env.ref('veterinaria.action_report_indicaciones').report_action(self)

    def action_ver_mascota(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'vet.mascota',
            'res_id': self.mascota_id.id,
            'view_mode': 'form',
        }


class VetAtencionLinea(models.Model):
    _name = 'vet.atencion.linea'
    _inherit = 'vet.linea.venta'
    _description = 'Servicio o producto de la atención'
    _order = 'atencion_id, sequence, id'
    _check_company_auto = True

    atencion_id = fields.Many2one('vet.atencion', string='Atención', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='atencion_id.company_id', store=True)
    currency_id = fields.Many2one(related='atencion_id.currency_id')
    es_aplicacion = fields.Selection(related='producto_id.vet_aplicacion', string='Aplicación')
    lote = fields.Char('Lote', help='Lote de la vacuna o del antiparasitario: sale en el carnet.')
    aplicacion_ids = fields.One2many('vet.aplicacion', 'linea_id', string='Anotada en el carnet')

    # Guardados en la línea para el reporte de atenciones.
    area = fields.Selection(related='atencion_id.area', store=True, string='Área')
    profesional_id = fields.Many2one(related='atencion_id.profesional_id', store=True, string='Atendió')
    mascota_id = fields.Many2one(related='atencion_id.mascota_id', store=True, string='Mascota')
    especie_id = fields.Many2one(related='atencion_id.mascota_id.especie_id', store=True, string='Especie')
    fecha = fields.Datetime(related='atencion_id.fecha_inicio', store=True, string='Fecha')
    estado = fields.Selection(related='atencion_id.estado', store=True, string='Estado')
    categoria_id = fields.Many2one(related='producto_id.categ_id', store=True, string='Categoría')

    def _vet_documento(self):
        return self.atencion_id
