# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .utiles import EMOJIS, edad_texto, fecha_corta

SEXOS = [
    ('macho', 'Macho'),
    ('hembra', 'Hembra'),
]


class VetMascota(models.Model):
    _name = 'vet.mascota'
    _description = 'Mascota'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name, id'
    _check_company_auto = True
    _rec_names_search = ['name', 'dueno_id.name', 'microchip']

    name = fields.Char('Nombre', required=True, tracking=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                 default=lambda self: self.env.company)
    active = fields.Boolean(default=True)
    foto = fields.Image('Foto', max_width=512, max_height=512)
    emoji = fields.Char(compute='_compute_emoji')
    dueno_id = fields.Many2one('res.partner', string='Dueño', required=True, tracking=True, index=True,
                               check_company=True)
    dueno_telefono = fields.Char('Teléfono del dueño', compute='_compute_dueno_telefono')
    especie_id = fields.Many2one('vet.especie', string='Especie', required=True, tracking=True)
    raza_id = fields.Many2one('vet.raza', string='Raza', domain="[('especie_id', '=', especie_id)]")
    sexo = fields.Selection(SEXOS, string='Sexo')
    castrado = fields.Boolean('Castrado/a')
    fecha_nacimiento = fields.Date('Nacimiento', help='Si no se sabe, una fecha aproximada.')
    edad = fields.Char('Edad', compute='_compute_edad')
    color = fields.Char('Color y señas')
    microchip = fields.Char('Microchip', copy=False)
    alertas = fields.Char('Cuidado', tracking=True,
                          help='Se muestra en rojo en el tablero y en cada atención: muerde, usar bozal, epiléptico...')
    alergias = fields.Text('Alergias y enfermedades crónicas')
    alimentacion = fields.Char('Come', help='Alimento habitual, para la internación y el hotel.')
    fallecida = fields.Boolean('Falleció', tracking=True, copy=False)
    fecha_fallecimiento = fields.Date('Fecha de fallecimiento', copy=False)

    peso_ids = fields.One2many('vet.peso', 'mascota_id', string='Pesos')
    peso_actual = fields.Float('Peso (kg)', compute='_compute_peso_actual', store=True, digits=(6, 2))
    atencion_ids = fields.One2many('vet.atencion', 'mascota_id', string='Atenciones')
    atencion_count = fields.Integer('Cantidad de atenciones', compute='_compute_conteos')
    aplicacion_ids = fields.One2many('vet.aplicacion', 'mascota_id', string='Vacunas y desparasitaciones')
    aplicacion_count = fields.Integer('Vacunas', compute='_compute_conteos')
    internacion_ids = fields.One2many('vet.internacion', 'mascota_id', string='Internaciones y estadías')
    internacion_count = fields.Integer('Internaciones', compute='_compute_conteos')
    proxima_dosis = fields.Date('Próxima dosis', compute='_compute_proxima_dosis')
    proxima_dosis_texto = fields.Char('Le toca', compute='_compute_proxima_dosis')

    _sql_constraints = [
        ('microchip_unico', 'UNIQUE(company_id, microchip)', 'Ya hay una mascota con ese microchip.'),
    ]

    @api.depends('especie_id.icono')
    def _compute_emoji(self):
        for mascota in self:
            mascota.emoji = EMOJIS.get(mascota.especie_id.icono, EMOJIS['otro'])

    @api.depends('dueno_id.mobile', 'dueno_id.phone')
    def _compute_dueno_telefono(self):
        for mascota in self:
            mascota.dueno_telefono = mascota.dueno_id.mobile or mascota.dueno_id.phone

    @api.depends('fecha_nacimiento', 'fallecida', 'fecha_fallecimiento')
    def _compute_edad(self):
        hoy = fields.Date.context_today(self)
        for mascota in self:
            hasta = mascota.fecha_fallecimiento if mascota.fallecida and mascota.fecha_fallecimiento else hoy
            mascota.edad = edad_texto(mascota.fecha_nacimiento, hasta)

    @api.depends('peso_ids.peso', 'peso_ids.fecha')
    def _compute_peso_actual(self):
        for mascota in self:
            ultimo = mascota.peso_ids.sorted(lambda peso: (peso.fecha, peso.id))[-1:]
            mascota.peso_actual = ultimo.peso

    def _compute_conteos(self):
        for mascota in self:
            mascota.atencion_count = len(mascota.atencion_ids)
            mascota.aplicacion_count = len(mascota.aplicacion_ids)
            mascota.internacion_count = len(mascota.internacion_ids)

    @api.depends('aplicacion_ids.proxima_fecha', 'aplicacion_ids.renovada')
    def _compute_proxima_dosis(self):
        for mascota in self:
            pendientes = mascota.aplicacion_ids.filtered(
                lambda aplicacion: aplicacion.proxima_fecha and not aplicacion.renovada).sorted('proxima_fecha')
            primera = pendientes[:1]
            mascota.proxima_dosis = primera.proxima_fecha
            mascota.proxima_dosis_texto = (f'{primera.producto_id.name} el {fecha_corta(primera.proxima_fecha)}'
                                           if primera else False)

    @api.depends('name', 'dueno_id.name')
    def _compute_display_name(self):
        # Con el dueño: en la veterinaria hay muchos "Toby".
        for mascota in self:
            mascota.display_name = f'{mascota.name} ({mascota.dueno_id.name})' if mascota.dueno_id else mascota.name

    @api.constrains('raza_id', 'especie_id')
    def _check_raza(self):
        for mascota in self:
            if mascota.raza_id and mascota.raza_id.especie_id != mascota.especie_id:
                raise ValidationError(f'{mascota.raza_id.name} no es una raza de {mascota.especie_id.name}.')

    @api.constrains('fecha_nacimiento')
    def _check_nacimiento(self):
        hoy = fields.Date.context_today(self)
        for mascota in self:
            if mascota.fecha_nacimiento and mascota.fecha_nacimiento > hoy:
                raise ValidationError('La fecha de nacimiento no puede ser futura.')

    @api.onchange('especie_id')
    def _onchange_especie_id(self):
        if self.raza_id and self.raza_id.especie_id != self.especie_id:
            self.raza_id = False

    def _vet_terminacion(self):
        """Para los mensajes: 'listo' o 'lista' según el sexo; 'listo/a' si no se cargó."""
        self.ensure_one()
        return {'macho': 'o', 'hembra': 'a'}.get(self.sexo, 'o/a')

    def write(self, vals):
        if vals.get('fallecida') and 'fecha_fallecimiento' not in vals:
            vals = dict(vals, fecha_fallecimiento=fields.Date.context_today(self))
        return super().write(vals)

    # Línea de tiempo (static/src/ficha)

    @api.model
    def vet_linea_tiempo(self, mascota_id):
        """Todo lo que se le hizo a la mascota, de lo más nuevo a lo más viejo, y la evolución del peso."""
        mascota = self.browse(mascota_id).exists()
        if not mascota:
            return {'eventos': [], 'pesos': []}
        mascota.check_access('read')
        eventos = []
        for atencion in mascota.atencion_ids.filtered(lambda a: a.estado in ('lista', 'cobrada')):
            clinica = atencion.area == 'consultorio'
            detalle = (atencion.diagnostico or atencion.motivo) if clinica else atencion.estetica_observaciones
            # Las vacunas tienen su propio evento: una visita que fue solo para vacunarse no se repite.
            hecho = atencion.linea_ids.producto_id.filtered(lambda producto: not producto.vet_aplicacion)
            if clinica and not hecho and not (atencion.diagnostico or atencion.anamnesis):
                continue
            eventos.append({
                'tipo': 'consulta' if clinica else 'estetica',
                'fecha': fields.Date.to_string(atencion._dia_local(atencion.fecha_inicio)),
                'titulo': ' + '.join(hecho.mapped('name')) or ('Consulta' if clinica else 'Baño y peluquería'),
                'detalle': detalle or '',
                'quien': atencion.profesional_id.name or '',
                'modelo': 'vet.atencion',
                'id': atencion.id,
            })
        for aplicacion in mascota.aplicacion_ids:
            proxima = (f'Próxima: {fecha_corta(aplicacion.proxima_fecha)} de {aplicacion.proxima_fecha.year}'
                       if aplicacion.proxima_fecha and not aplicacion.renovada else '')
            eventos.append({
                'tipo': 'vacuna' if aplicacion.tipo == 'vacuna' else 'desparasitacion',
                'fecha': fields.Date.to_string(aplicacion.fecha),
                'titulo': aplicacion.producto_id.name,
                'detalle': ' · '.join(parte for parte in (proxima, aplicacion.lote and f'Lote {aplicacion.lote}')
                                      if parte),
                'quien': aplicacion.profesional_id.name or '',
                'modelo': 'vet.aplicacion',
                'id': aplicacion.id,
            })
        for internacion in mascota.internacion_ids.filtered(lambda i: i.estado != 'cancelada'):
            dias = internacion.dias_a_cobrar if internacion.estado != 'activa' else internacion.dias_hasta_hoy
            eventos.append({
                'tipo': internacion.tipo,
                'fecha': fields.Date.to_string(fields.Date.to_date(internacion.ingreso)),
                'titulo': (f'{internacion._tipo_texto()} en {internacion.lugar_id.name}'
                           f'{" (sigue adentro)" if internacion.estado == "activa" else ""}'),
                'detalle': ' · '.join(parte for parte in (f'{dias} día{"s" if dias != 1 else ""}',
                                                          internacion.motivo) if parte),
                'quien': internacion.profesional_id.name or '',
                'modelo': 'vet.internacion',
                'id': internacion.id,
            })
        if mascota.fallecida and mascota.fecha_fallecimiento:
            eventos.append({
                'tipo': 'fallecimiento', 'fecha': fields.Date.to_string(mascota.fecha_fallecimiento),
                'titulo': 'Falleció', 'detalle': '', 'quien': '', 'modelo': False, 'id': False,
            })
        if mascota.fecha_nacimiento:
            eventos.append({
                'tipo': 'nacimiento', 'fecha': fields.Date.to_string(mascota.fecha_nacimiento),
                'titulo': 'Nació', 'detalle': '', 'quien': '', 'modelo': False, 'id': False,
            })
        orden = {'nacimiento': 0}
        eventos.sort(key=lambda evento: (evento['fecha'], orden.get(evento['tipo'], 1)), reverse=True)
        pesos = [{'fecha': fields.Date.to_string(peso.fecha), 'peso': peso.peso}
                 for peso in mascota.peso_ids.sorted(lambda peso: (peso.fecha, peso.id))]
        return {'eventos': eventos, 'pesos': pesos}

    # Botones

    def _vet_accion(self, xml_id, contexto=None):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(xml_id)
        action['domain'] = [('mascota_id', '=', self.id)]
        action['context'] = {'default_mascota_id': self.id, **(contexto or {})}
        return action

    def action_ver_atenciones(self):
        action = self._vet_accion('veterinaria.action_vet_atencion')
        action['views'] = [(False, 'list'), (False, 'form'), (False, 'calendar')]
        action['view_mode'] = 'list,form,calendar'
        return action

    def action_ver_aplicaciones(self):
        return self._vet_accion('veterinaria.action_vet_aplicacion')

    def action_ver_internaciones(self):
        return self._vet_accion('veterinaria.action_vet_internacion')

    def action_ver_pesos(self):
        return self._vet_accion('veterinaria.action_vet_peso')

    def action_nueva_atencion(self):
        """Turno nuevo para la mascota, en la agenda del consultorio."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Turno para {self.name}',
            'res_model': 'vet.atencion',
            'view_mode': 'form',
            'target': 'current',
            'context': {'default_mascota_id': self.id, 'default_area': 'consultorio'},
        }

    def action_imprimir_carnet(self):
        return self.env.ref('veterinaria.action_report_carnet').report_action(self)

    def action_imprimir_historia(self):
        return self.env.ref('veterinaria.action_report_historia').report_action(self)
