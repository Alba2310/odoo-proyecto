# -*- coding: utf-8 -*-
from datetime import timedelta
from urllib.parse import quote

from odoo import api, fields, models
from odoo.exceptions import UserError

from .utiles import MESES, fecha_corta, guaranies, mes_y_anio, numero_whatsapp, primer_nombre

ESTADOS_CUOTA = [
    ('pendiente', 'Pendiente'),
    ('parcial', 'Pago parcial'),
    ('pagada', 'Pagada'),
]
CONCEPTOS_CARGO = [
    ('ande', 'ANDE (luz)'),
    ('agua', 'Agua'),
    ('expensas', 'Expensas'),
    ('reparacion', 'Reparación'),
    ('recargo', 'Recargo por atraso'),
    ('otro', 'Otro'),
]
# Avisos de pago por WhatsApp: el primero unos días antes de vencer, otro el día que vence y, mientras no pague,
# cada tantos días.
DIAS_AVISO_ANTES = 3
DIAS_ENTRE_AVISOS = 3
# Cómo paga cada inquilino: una cuota pagada hasta estos días después de vencer cuenta como pagada a tiempo.
DIAS_TOLERANCIA = 3
CALIFICACIONES = [
    ('0', 'Sin datos'),
    ('1', 'Se atrasa seguido'),
    ('2', 'A veces se atrasa'),
    ('3', 'Paga a tiempo'),
]


def calificar(cuotas, hoy):
    """Cómo paga un inquilino según sus cuotas pagadas y vencidas: (estrellas de CALIFICACIONES, texto)."""
    evaluables = cuotas.filtered(lambda c: c.estado == 'pagada' or c.fecha_vencimiento < hoy)
    if not evaluables:
        return '0', 'Todavía no tiene cuotas vencidas'
    atrasos = []
    for cuota in evaluables:
        hasta = cuota.fecha_pago if cuota.estado == 'pagada' else hoy
        atrasos.append(max((hasta - cuota.fecha_vencimiento).days, 0))
    a_tiempo = sum(1 for dias in atrasos if dias <= DIAS_TOLERANCIA)
    proporcion = a_tiempo / len(atrasos)
    estrellas = '3' if proporcion >= 0.9 else '2' if proporcion >= 0.6 else '1'
    texto = f'{a_tiempo} de {len(atrasos)} cuotas a tiempo'
    promedio = round(sum(atrasos) / len(atrasos))
    if promedio:
        texto += f' · atraso promedio: {promedio} día' + ('s' if promedio != 1 else '')
    return estrellas, texto


class AlquilerCuota(models.Model):
    """El alquiler de un mes de un contrato, más los cargos extra de ese mes (ANDE, agua, reparaciones).
    Las crea el contrato (ver AlquilerContrato._generar_cuotas)."""
    _name = 'alquiler.cuota'
    _description = 'Cuota de alquiler'
    _order = 'fecha_vencimiento desc, id desc'

    name = fields.Char('Mes', compute='_compute_name', store=True)
    contrato_id = fields.Many2one('alquiler.contrato', string='Contrato', required=True, ondelete='cascade',
                                  index=True)
    inquilino_id = fields.Many2one(related='contrato_id.inquilino_id', store=True, string='Inquilino')
    unidad_id = fields.Many2one(related='contrato_id.unidad_id', store=True, string='Unidad')
    propiedad_id = fields.Many2one(related='contrato_id.propiedad_id', store=True, string='Propiedad')
    company_id = fields.Many2one(related='contrato_id.company_id', store=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    telefono = fields.Char(related='contrato_id.telefono')
    periodo = fields.Date('Mes del alquiler', required=True, help='Primer día del mes que se paga.')
    fecha_vencimiento = fields.Date('Vence', required=True)
    monto = fields.Monetary('Alquiler', required=True)
    cargo_ids = fields.One2many('alquiler.cuota.cargo', 'cuota_id', string='Detalle de los cargos')
    cargos = fields.Monetary('Cargos extra', compute='_compute_pagos', store=True,
                             help='ANDE, agua, reparaciones y otros gastos que se le cobran al inquilino con la cuota.')
    total = fields.Monetary('Total', compute='_compute_pagos', store=True)
    pago_ids = fields.One2many('alquiler.pago', 'cuota_id', string='Pagos')
    pagado = fields.Monetary('Pagado', compute='_compute_pagos', store=True)
    saldo = fields.Monetary('Falta pagar', compute='_compute_pagos', store=True)
    estado = fields.Selection(ESTADOS_CUOTA, string='Estado', compute='_compute_pagos', store=True)
    fecha_pago = fields.Date('Pagada el', compute='_compute_pagos', store=True)
    dias_atraso = fields.Integer('Días de atraso', compute='_compute_atraso')
    atrasada = fields.Boolean('Atrasada', compute='_compute_atraso')
    proximo_aviso = fields.Date('Próximo aviso', compute='_compute_proximo_aviso', store=True, readonly=False,
                                precompute=True,
                                help='Desde ese día la cuota aparece en "Avisos de hoy" para mandar el aviso de pago.')
    ultimo_aviso = fields.Date('Último aviso', readonly=True, copy=False)
    avisos_enviados = fields.Integer('Avisos enviados', readonly=True, copy=False)
    whatsapp_url = fields.Char('Enlace de WhatsApp', compute='_compute_whatsapp_url')

    _sql_constraints = [
        ('mes_unico', 'unique(contrato_id, periodo)', 'El contrato ya tiene la cuota de ese mes.'),
        ('monto_positivo', 'CHECK(monto > 0)', 'El monto de la cuota tiene que ser mayor a cero.'),
    ]

    @api.model
    def _dominio_vencidas(self):
        return [('estado', '!=', 'pagada'), ('fecha_vencimiento', '<', fields.Date.context_today(self))]

    @api.depends('periodo')
    def _compute_name(self):
        for cuota in self:
            periodo = cuota.periodo
            cuota.name = f'{MESES[periodo.month - 1].capitalize()} {periodo.year}' if periodo else False

    @api.depends('name', 'inquilino_id.name')
    def _compute_display_name(self):
        for cuota in self:
            cuota.display_name = ' · '.join(parte for parte in (cuota.inquilino_id.name, cuota.name) if parte)

    @api.depends('monto', 'cargo_ids.monto', 'pago_ids.monto', 'pago_ids.fecha')
    def _compute_pagos(self):
        for cuota in self:
            moneda = cuota.currency_id or self.env.company.currency_id
            cuota.cargos = sum(cuota.cargo_ids.mapped('monto'))
            cuota.total = cuota.monto + cuota.cargos
            cuota.pagado = sum(cuota.pago_ids.mapped('monto'))
            cuota.saldo = cuota.total - cuota.pagado
            cuota.fecha_pago = max(cuota.pago_ids.mapped('fecha'), default=False)
            if cuota.pago_ids and moneda.compare_amounts(cuota.saldo, 0) <= 0:
                cuota.estado = 'pagada'
            else:
                cuota.estado = 'parcial' if cuota.pago_ids else 'pendiente'

    @api.depends('fecha_vencimiento', 'estado')
    def _compute_atraso(self):
        hoy = fields.Date.context_today(self)
        for cuota in self:
            dias = (hoy - cuota.fecha_vencimiento).days if cuota.fecha_vencimiento and cuota.estado != 'pagada' else 0
            cuota.dias_atraso = max(dias, 0)
            cuota.atrasada = dias > 0

    @api.depends('fecha_vencimiento')
    def _compute_proximo_aviso(self):
        for cuota in self:
            vence = cuota.fecha_vencimiento
            cuota.proximo_aviso = vence - timedelta(days=DIAS_AVISO_ANTES) if vence else False

    def _detalle(self):
        """'Gs. 1.300.000' o, con cargos, 'alquiler Gs. 1.300.000 + Agua Gs. 85.000'."""
        self.ensure_one()
        if not self.cargo_ids:
            return guaranies(self.monto)
        conceptos = dict(CONCEPTOS_CARGO)
        partes = [f'alquiler {guaranies(self.monto)}'] + [
            f'{cargo.detalle or conceptos[cargo.concepto]} {guaranies(cargo.monto)}' for cargo in self.cargo_ids]
        return ' + '.join(partes)

    def _texto_whatsapp(self, hoy=None):
        self.ensure_one()
        hoy = hoy or fields.Date.context_today(self)
        nombre = primer_nombre(self.inquilino_id.name)
        alquiler = f'alquiler de {mes_y_anio(self.periodo)} ({self.unidad_id.display_name})'
        monto = guaranies(self.saldo)
        if self.cargo_ids and not self.pagado:
            monto += f' ({self._detalle()})'
        if hoy < self.fecha_vencimiento:
            return (f'¡Hola {nombre}! Te recordamos que el {fecha_corta(self.fecha_vencimiento)} vence el {alquiler}: '
                    f'{monto}. ¡Gracias!')
        if hoy == self.fecha_vencimiento:
            return f'¡Hola {nombre}! Te recordamos que hoy vence el {alquiler}: {monto}. ¡Gracias!'
        return (f'¡Hola {nombre}! El {alquiler} venció el {fecha_corta(self.fecha_vencimiento)} y figura pendiente: '
                f'{monto}. Si ya pagaste, avisanos por acá así lo registramos. ¡Gracias!')

    @api.depends('inquilino_id.phone', 'inquilino_id.mobile', 'saldo', 'periodo', 'fecha_vencimiento')
    def _compute_whatsapp_url(self):
        for cuota in self:
            codigo_pais = str(cuota.company_id.country_id.phone_code or 595)
            numero = numero_whatsapp(cuota.inquilino_id.mobile or cuota.inquilino_id.phone, codigo_pais)
            if numero and cuota.periodo and cuota.fecha_vencimiento:
                cuota.whatsapp_url = f'https://wa.me/{numero}?text={quote(cuota._texto_whatsapp())}'
            else:
                cuota.whatsapp_url = False

    def _registrar_aviso(self, hoy):
        """Anota el aviso y cuándo toca el siguiente: el día que vence o, si ya venció, en unos días."""
        for cuota in self:
            if hoy < cuota.fecha_vencimiento:
                proximo = cuota.fecha_vencimiento
            else:
                proximo = hoy + timedelta(days=DIAS_ENTRE_AVISOS)
            cuota.write({'ultimo_aviso': hoy, 'avisos_enviados': cuota.avisos_enviados + 1, 'proximo_aviso': proximo})

    def action_whatsapp(self):
        """Abre WhatsApp (web o la aplicación) con el aviso de pago escrito; solo falta tocar Enviar.
        Es gratis y no necesita la API de WhatsApp Business."""
        self.ensure_one()
        if self.estado == 'pagada':
            raise UserError(f'La cuota de {self.name} de {self.inquilino_id.name} ya está pagada.')
        if not self.whatsapp_url:
            raise UserError(f'{self.inquilino_id.name} no tiene teléfono cargado.')
        url = self.whatsapp_url
        self._registrar_aviso(fields.Date.context_today(self))
        self.contrato_id.message_post(
            body=f'Aviso de pago por WhatsApp: cuota de {self.name} ({guaranies(self.saldo)}).')
        return {'type': 'ir.actions.act_url', 'url': url, 'target': 'new'}

    def action_registrar_pago(self):
        self.ensure_one()
        if self.estado == 'pagada':
            raise UserError(f'La cuota de {self.name} de {self.inquilino_id.name} ya está pagada.')
        return {
            'type': 'ir.actions.act_window',
            'name': f'Registrar pago · {self.inquilino_id.name} · {self.name}',
            'res_model': 'alquiler.pago',
            'view_mode': 'form',
            'views': [(self.env.ref('alquileres.view_alquiler_pago_form_registrar').id, 'form')],
            'target': 'new',
            'context': {'default_cuota_id': self.id, 'default_monto': self.saldo},
        }

    @api.ondelete(at_uninstall=False)
    def _unlink_sin_pagos(self):
        if self.pago_ids:
            raise UserError('No se puede borrar una cuota que tiene pagos registrados.')


class AlquilerCuotaCargo(models.Model):
    """Un gasto que se le cobra al inquilino junto con el alquiler del mes: la ANDE, el agua, una reparación..."""
    _name = 'alquiler.cuota.cargo'
    _description = 'Cargo extra de una cuota'
    _order = 'cuota_id, id'

    cuota_id = fields.Many2one('alquiler.cuota', string='Cuota', required=True, ondelete='cascade', index=True)
    concepto = fields.Selection(CONCEPTOS_CARGO, string='Concepto', required=True, default='ande')
    detalle = fields.Char('Detalle', help='Por ejemplo: ANDE de septiembre.')
    monto = fields.Monetary('Monto', required=True)
    currency_id = fields.Many2one(related='cuota_id.currency_id')
    mantenimiento_id = fields.Many2one('alquiler.mantenimiento', string='Reparación', readonly=True,
                                       ondelete='set null')

    _sql_constraints = [
        ('monto_positivo', 'CHECK(monto > 0)', 'El monto del cargo tiene que ser mayor a cero.'),
    ]
