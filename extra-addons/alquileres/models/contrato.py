# -*- coding: utf-8 -*-
import calendar
from datetime import timedelta
from urllib.parse import quote

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .cuota import CALIFICACIONES, calificar
from .utiles import en_letras, fecha_corta, fecha_larga, guaranies, numero_whatsapp, primer_nombre

ESTADOS_CONTRATO = [
    ('borrador', 'Borrador'),
    ('vigente', 'Vigente'),
    ('terminado', 'Terminado'),
]
# Las cuotas se crean unos días antes de vencer, así entran en los avisos de 3 días antes.
DIAS_ANTICIPACION = 10
# Desde cuántos días antes se avisa al inquilino que vence el contrato o que sube el alquiler.
DIAS_AVISO_VENCIMIENTO = 60
DIAS_AVISO_REAJUSTE = 30


def vencimiento_del_mes(mes, dia_pago):
    """El día de pago dentro del mes; si el mes es más corto (un 31 en febrero), el último día del mes."""
    return mes.replace(day=min(dia_pago, calendar.monthrange(mes.year, mes.month)[1]))


def reajustar(monto, porcentaje):
    """El alquiler con el reajuste anual, redondeado a miles."""
    return round(monto * (1 + porcentaje / 100), -3)


def siguiente_aniversario(fecha, hoy):
    """`fecha` o, si ya pasó (o es hoy), el primero de sus aniversarios que viene después de `hoy`."""
    while fecha <= hoy:
        fecha += relativedelta(years=1)
    return fecha


class AlquilerContrato(models.Model):
    """Contrato de alquiler de una unidad. Mientras está vigente, se crea solo la cuota de cada mes."""
    _name = 'alquiler.contrato'
    _description = 'Contrato de alquiler'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'fecha_inicio desc, id desc'
    # El encargado de cobros solo lee los contratos, pero deja en ellos el registro de los avisos que manda.
    _mail_post_access = 'read'

    name = fields.Char('Número', readonly=True, copy=False, default='Nuevo')
    unidad_id = fields.Many2one('alquiler.unidad', string='Unidad', required=True, tracking=True, index=True)
    propiedad_id = fields.Many2one(related='unidad_id.propiedad_id', store=True, string='Propiedad')
    company_id = fields.Many2one(related='unidad_id.company_id', store=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    inquilino_id = fields.Many2one('res.partner', string='Inquilino', required=True, tracking=True, index=True)
    telefono = fields.Char(related='inquilino_id.phone', readonly=False, string='Teléfono (WhatsApp)')
    garante_id = fields.Many2one('res.partner', string='Garante', tracking=True)
    # Sin fecha por defecto: el día de pago se propone desde esta fecha, y con una fecha de hoy ya cargada no se
    # sabría si el día de pago lo eligió el usuario o salió de ella.
    fecha_inicio = fields.Date('Desde', required=True, tracking=True)
    fecha_fin = fields.Date('Hasta', tracking=True, help='Vacío si el contrato no tiene fecha de fin.')
    fecha_salida = fields.Date('Se va el', readonly=True, copy=False, tracking=True,
                               help='Se terminó el contrato con un día de salida que todavía no llegó: hasta ese día '
                                    'sigue vigente y al día siguiente se termina solo.')
    monto = fields.Monetary('Alquiler mensual', required=True, tracking=True,
                            help='Si cambia (reajuste), las cuotas que se crean desde ahí usan el monto nuevo.')
    # Alquiler de una renovación que todavía no empezó: el cron lo pasa a "monto" el día que empieza.
    monto_renovacion = fields.Monetary('Alquiler de la renovación', readonly=True, copy=False)
    fecha_renovacion = fields.Date('Renovación desde', readonly=True, copy=False)
    dia_pago = fields.Integer('Día de pago', compute='_compute_dia_pago', store=True, readonly=False,
                              precompute=True, tracking=True,
                              help='Día de cada mes en que vence el alquiler. Si el mes es más corto, vence el último '
                                   'día. Si está vacío, se propone el mismo día en que empieza el contrato.')
    estado = fields.Selection(ESTADOS_CONTRATO, string='Estado', default='borrador', required=True, readonly=True,
                              tracking=True, copy=False)
    nota = fields.Text('Notas')
    clausulas_extra = fields.Text('Cláusulas adicionales',
                                  help='Se agregan al final del contrato impreso. Por ejemplo: se permite una mascota.')

    # Reajuste anual
    reajuste_pct = fields.Float('Reajuste anual (%)', tracking=True,
                                help='Cada año, en la fecha de reajuste, el alquiler sube este porcentaje '
                                     '(redondeado a miles).')
    fecha_reajuste = fields.Date('Próximo reajuste', compute='_compute_fecha_reajuste', store=True, readonly=False,
                                 precompute=True, tracking=True)
    monto_reajustado = fields.Monetary('Alquiler después del reajuste', compute='_compute_monto_reajustado')

    # Depósito de garantía: al terminar se usa para cubrir lo que quedó debiendo y los daños.
    deposito = fields.Monetary('Depósito de garantía')
    deposito_aplicado = fields.Monetary('Usado para pagar deudas', readonly=True, copy=False)
    deposito_descuento = fields.Monetary('Descuento por daños', readonly=True, copy=False)
    deposito_motivo = fields.Char('Motivo del descuento', readonly=True, copy=False)
    deposito_a_devolver = fields.Monetary('Depósito a devolver', compute='_compute_deposito_a_devolver', store=True)
    deposito_devuelto = fields.Date('Depósito devuelto el', readonly=True, copy=False, tracking=True)

    cuota_ids = fields.One2many('alquiler.cuota', 'contrato_id', string='Cuotas')
    pago_ids = fields.One2many('alquiler.pago', 'contrato_id', string='Pagos')
    acta_ids = fields.One2many('alquiler.acta', 'contrato_id', string='Actas de entrega')
    cuota_count = fields.Integer('Cantidad de cuotas', compute='_compute_cantidades')
    pago_count = fields.Integer('Cantidad de pagos', compute='_compute_cantidades')
    acta_count = fields.Integer('Cantidad de actas', compute='_compute_cantidades')
    deuda = fields.Monetary('Deuda', compute='_compute_deuda', help='Cuotas vencidas sin pagar.')
    cuotas_atrasadas = fields.Integer('Cuotas atrasadas', compute='_compute_deuda')
    proximo_vencimiento = fields.Date('Próximo vencimiento', compute='_compute_deuda')
    vence_pronto = fields.Boolean('Vence pronto', compute='_compute_avisos_contrato')
    reajuste_pronto = fields.Boolean('Reajuste pronto', compute='_compute_avisos_contrato')
    puntaje = fields.Selection(CALIFICACIONES, string='Cómo paga', compute='_compute_puntaje')
    puntaje_texto = fields.Char('Pagos a tiempo', compute='_compute_puntaje')

    _sql_constraints = [
        ('dia_pago_valido', 'CHECK(dia_pago BETWEEN 1 AND 31)', 'El día de pago tiene que estar entre 1 y 31.'),
        ('monto_positivo', 'CHECK(monto > 0)', 'El alquiler mensual tiene que ser mayor a cero.'),
        ('reajuste_valido', 'CHECK(reajuste_pct >= 0)', 'El reajuste no puede ser negativo.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code('alquiler.contrato') or 'Nuevo'
        contratos = super().create(vals_list)
        contratos.inquilino_id.sudo().alquiler_es_inquilino = True
        return contratos

    def write(self, vals):
        resultado = super().write(vals)
        if vals.get('inquilino_id'):
            self.inquilino_id.sudo().alquiler_es_inquilino = True
        return resultado

    @api.ondelete(at_uninstall=False)
    def _unlink_sin_pagos(self):
        if self.pago_ids:
            raise UserError('Este contrato tiene pagos registrados: termínelo en lugar de borrarlo.')

    @api.depends('fecha_inicio')
    def _compute_dia_pago(self):
        # Solo se propone si está vacío: el día que eligió el usuario no se pisa al cambiar la fecha de inicio.
        for contrato in self:
            if not contrato.dia_pago:
                contrato.dia_pago = contrato.fecha_inicio.day if contrato.fecha_inicio else 0
            else:
                contrato.dia_pago = contrato.dia_pago

    @api.depends('fecha_inicio', 'reajuste_pct')
    def _compute_fecha_reajuste(self):
        # Se propone al año de empezar o, si el contrato empezó hace más de un año, en el próximo aniversario: el
        # alquiler que se carga es el de ahora, con los reajustes que ya hubo. Si ya tiene una fecha (porque se
        # cargó o ya hubo reajustes), se respeta.
        hoy = fields.Date.context_today(self)
        for contrato in self:
            if not contrato.reajuste_pct:
                contrato.fecha_reajuste = False
            elif not contrato.fecha_reajuste and contrato.fecha_inicio:
                contrato.fecha_reajuste = siguiente_aniversario(contrato.fecha_inicio + relativedelta(years=1), hoy)
            else:
                contrato.fecha_reajuste = contrato.fecha_reajuste

    @api.depends('monto', 'reajuste_pct')
    def _compute_monto_reajustado(self):
        for contrato in self:
            contrato.monto_reajustado = reajustar(contrato.monto, contrato.reajuste_pct)

    @api.depends('deposito', 'deposito_aplicado', 'deposito_descuento')
    def _compute_deposito_a_devolver(self):
        for contrato in self:
            contrato.deposito_a_devolver = max(
                contrato.deposito - contrato.deposito_aplicado - contrato.deposito_descuento, 0)

    @api.onchange('unidad_id')
    def _onchange_unidad_id(self):
        if self.unidad_id and not self.monto:
            self.monto = self.unidad_id.alquiler_sugerido

    def _compute_cantidades(self):
        for contrato in self:
            contrato.cuota_count = len(contrato.cuota_ids)
            contrato.pago_count = len(contrato.pago_ids)
            contrato.acta_count = len(contrato.acta_ids)

    @api.depends('cuota_ids.saldo', 'cuota_ids.estado', 'cuota_ids.fecha_vencimiento')
    def _compute_deuda(self):
        hoy = fields.Date.context_today(self)
        for contrato in self:
            pendientes = contrato.cuota_ids.filtered(lambda c: c.estado != 'pagada')
            vencidas = pendientes.filtered(lambda c: c.fecha_vencimiento < hoy)
            contrato.deuda = sum(vencidas.mapped('saldo'))
            contrato.cuotas_atrasadas = len(vencidas)
            contrato.proximo_vencimiento = min((pendientes - vencidas).mapped('fecha_vencimiento'),
                                               default=contrato._proximo_vencimiento_sin_cuota())

    def _proximo_vencimiento_sin_cuota(self):
        """Vencimiento del mes siguiente a la última cuota, que todavía no se creó."""
        if self.estado != 'vigente' or not self.cuota_ids:
            return False
        mes = max(self.cuota_ids.mapped('periodo')) + relativedelta(months=1)
        vence = vencimiento_del_mes(mes, self.dia_pago)
        return False if self.fecha_fin and vence > self.fecha_fin else vence

    @api.depends('estado', 'fecha_fin', 'fecha_salida', 'fecha_reajuste')
    def _compute_avisos_contrato(self):
        hoy = fields.Date.context_today(self)
        for contrato in self:
            vigente = contrato.estado == 'vigente'
            # Si ya se sabe que se va, no hay que avisarle que vence ni proponerle renovar.
            contrato.vence_pronto = bool(vigente and contrato.fecha_fin and not contrato.fecha_salida
                                         and contrato.fecha_fin <= hoy + timedelta(days=DIAS_AVISO_VENCIMIENTO))
            contrato.reajuste_pronto = bool(vigente and contrato.reajuste_pct and contrato.fecha_reajuste
                                            and contrato.fecha_reajuste <= hoy + timedelta(days=DIAS_AVISO_REAJUSTE))

    @api.depends('cuota_ids.estado', 'cuota_ids.fecha_pago')
    def _compute_puntaje(self):
        hoy = fields.Date.context_today(self)
        for contrato in self:
            contrato.puntaje, contrato.puntaje_texto = calificar(contrato.cuota_ids, hoy)

    @api.constrains('fecha_inicio', 'fecha_fin')
    def _check_fechas(self):
        for contrato in self:
            if contrato.fecha_fin and contrato.fecha_fin < contrato.fecha_inicio:
                raise ValidationError('El contrato no puede terminar antes de empezar.')

    @api.constrains('estado', 'unidad_id')
    def _check_un_contrato_vigente(self):
        for contrato in self.filtered(lambda c: c.estado == 'vigente'):
            otro = self.search([('id', '!=', contrato.id), ('unidad_id', '=', contrato.unidad_id.id),
                                ('estado', '=', 'vigente')], limit=1)
            if otro:
                raise ValidationError(
                    f'{contrato.unidad_id.display_name} ya está alquilada a {otro.inquilino_id.name} '
                    f'(contrato {otro.name}). Termine ese contrato antes de activar otro.')

    def action_activar(self):
        hoy = fields.Date.context_today(self)
        for contrato in self:
            if contrato.estado != 'borrador':
                raise UserError(f'El contrato {contrato.name} ya se activó.')
            # El alquiler que se cargó es el de ahora: los reajustes que ya tendrían que haber pasado están
            # incluidos, así que ni las cuotas atrasadas ni el cron los vuelven a aplicar.
            if contrato.reajuste_pct and contrato.fecha_reajuste and contrato.fecha_reajuste <= hoy:
                contrato.fecha_reajuste = siguiente_aniversario(contrato.fecha_reajuste, hoy)
        self.write({'estado': 'vigente'})
        self._generar_cuotas()
        return True

    def action_terminar(self):
        """Abre la ventana para terminar el contrato y liquidar el depósito."""
        self.ensure_one()
        if self.estado != 'vigente':
            raise UserError(f'Solo se puede terminar un contrato vigente ({self.name}).')
        contexto = {'default_contrato_id': self.id}
        if self.fecha_salida:
            # Ya tiene la salida programada: se abre con esos datos, para cambiarlos o terminarlo antes.
            contexto.update(default_fecha=self.fecha_salida, default_descuento=self.deposito_descuento,
                            default_motivo=self.deposito_motivo)
        return {
            'type': 'ir.actions.act_window',
            'name': f'Terminar contrato {self.name}',
            'res_model': 'alquiler.terminar.wizard',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': contexto,
        }

    def _terminar(self, fecha=None, descuento=0, motivo=False):
        """Termina el contrato el día `fecha` (hoy si no se dice): la unidad queda libre, se borran las cuotas sin
        pagar que vencen después y el depósito paga lo que quedó debiendo. `descuento` es lo que se descuenta del
        depósito por daños.

        Si ese día todavía no llegó, el inquilino sigue viviendo ahí: el contrato queda vigente hasta ese día (se
        siguen creando sus cuotas y la unidad sigue alquilada) y el cron lo termina al día siguiente, con el
        descuento que se cargó ahora (ver _cron_generar_cuotas)."""
        hoy = fields.Date.context_today(self)
        fecha = fecha or hoy
        for contrato in self:
            if contrato.estado != 'vigente':
                raise UserError(f'Solo se puede terminar un contrato vigente ({contrato.name}).')
            fin = contrato._fin_al_terminar(fecha)
            anterior = contrato.fecha_fin
            contrato.fecha_fin = fin
            contrato.cuota_ids.filtered(lambda c: c.fecha_vencimiento > fin and not c.pago_ids).unlink()
            # La cuota del mes de pago en que se va, solo por los días que vive ahí.
            contrato._ajustar_cuota_del_fin(anterior)
            if fin > hoy:
                contrato.write({
                    'fecha_salida': fin,
                    'deposito_descuento': descuento or 0,
                    'deposito_motivo': motivo if descuento else False,
                })
                contrato.message_post(body=(
                    f'El inquilino se va el {fecha_larga(fin)}: hasta ese día el contrato sigue vigente y se cobran '
                    'sus cuotas; al día siguiente se termina solo y se liquida el depósito.'))
                continue
            # Las cuotas que vencen hasta ese día, por si el cron todavía no las creó.
            contrato._generar_cuotas(hasta=fin)
            contrato.estado = 'terminado'
            disponible = contrato.deposito
            for cuota in contrato.cuota_ids.filtered(lambda c: c.estado != 'pagada').sorted('fecha_vencimiento'):
                monto = min(cuota.saldo, disponible)
                if monto <= 0:
                    break
                self.env['alquiler.pago'].create({
                    'cuota_id': cuota.id, 'fecha': fin, 'monto': monto, 'medio': 'deposito',
                })
                disponible -= monto
            descuento = min(descuento or 0, disponible)
            contrato.write({
                'deposito_aplicado': contrato.deposito - disponible,
                'deposito_descuento': descuento,
                'deposito_motivo': motivo if descuento else False,
            })
            contrato.message_post(body=(
                f'Contrato terminado el {fecha_larga(fin)}. Depósito: {guaranies(contrato.deposito)}; usado para '
                f'deudas: {guaranies(contrato.deposito_aplicado)}; descuento por daños: {guaranies(descuento)}; '
                f'a devolver: {guaranies(contrato.deposito_a_devolver)}.'))
        return True

    def _fin_al_terminar(self, fecha):
        """El último día del contrato si el inquilino se va el día `fecha`: no pasa del fin del contrato, salvo que
        se esté cambiando el día de una salida ya programada."""
        self.ensure_one()
        fin = fecha if self.fecha_salida else min(self.fecha_fin or fecha, fecha)
        return max(fin, self.fecha_inicio)

    def _deuda_al_terminar(self, fecha):
        """Lo que quedaría debiendo si el inquilino se va el día `fecha` (para la ventana de terminar): las cuotas
        sin pagar hasta ese día, la de ese mes de pago por los días que le tocan, y las que todavía no se crearon."""
        self.ensure_one()
        fin = self._fin_al_terminar(fecha)
        mes_fin = self._mes_del_dia(fin)
        deuda = 0
        for cuota in self.cuota_ids.filtered(lambda c: c.estado != 'pagada' and c.fecha_vencimiento <= fin):
            if cuota.periodo == mes_fin:
                deuda += self._cuota_hasta(cuota, fin, self.fecha_fin)['monto'] + cuota.cargos - cuota.pagado
            else:
                deuda += cuota.saldo
        return deuda + sum(valores['monto'] for valores in self._cuotas_por_crear(fin, fin=fin))

    def action_deposito_devuelto(self):
        self.write({'deposito_devuelto': fields.Date.context_today(self)})
        return True

    def action_renovar(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Renovar contrato {self.name}',
            'res_model': 'alquiler.renovar.wizard',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {'default_contrato_id': self.id},
        }

    def _inicio_renovacion(self):
        """El día en que empieza la renovación: el siguiente al fin del contrato (mañana, si no tiene fin). Si ya se
        renovó con un alquiler nuevo que todavía no empezó, el de esa renovación, que se está corrigiendo."""
        self.ensure_one()
        if self.fecha_renovacion:
            return self.fecha_renovacion
        return (self.fecha_fin or fields.Date.context_today(self)) + relativedelta(days=1)

    def _monto_para(self, vence):
        """Alquiler de la cuota que vence en `vence`: el de la renovación si ya empezó y, si ya llegó la fecha de
        reajuste, reajustado."""
        self.ensure_one()
        monto = self.monto
        if self.fecha_renovacion and vence >= self.fecha_renovacion:
            monto = self.monto_renovacion
        if self.reajuste_pct and self.fecha_reajuste and vence >= self.fecha_reajuste:
            monto = reajustar(monto, self.reajuste_pct)
        return monto

    def _generar_cuotas(self, hasta=None):
        """Crea las cuotas que faltan de los contratos vigentes, hasta las que vencen en la fecha `hasta`
        (por defecto, en los próximos días)."""
        hasta = hasta or fields.Date.context_today(self) + timedelta(days=DIAS_ANTICIPACION)
        return self.env['alquiler.cuota'].create(self._cuotas_por_crear(hasta))

    def _periodo(self, mes):
        """Primer y último día del mes de pago `mes` (el `periodo` de una cuota): el alquiler se paga por adelantado,
        así que va del día de pago de ese mes al día anterior al día de pago del mes siguiente."""
        self.ensure_one()
        return (vencimiento_del_mes(mes, self.dia_pago),
                vencimiento_del_mes(mes + relativedelta(months=1), self.dia_pago) - timedelta(days=1))

    def _mes_del_dia(self, fecha):
        """El mes de pago (`periodo` de la cuota) en el que cae el día `fecha`."""
        self.ensure_one()
        mes = fecha.replace(day=1)
        return mes - relativedelta(months=1) if fecha < vencimiento_del_mes(mes, self.dia_pago) else mes

    def _cuotas_por_crear(self, hasta, fin=None):
        """Los valores de las cuotas que faltan de los contratos vigentes, hasta las que vencen en la fecha `hasta`.
        Cada cuota paga un mes de pago (ver _periodo) y vence el primer día de ese mes en que el inquilino vive ahí:
        el día de pago o, en la primera, el día que empieza el contrato. Si el contrato empieza o termina a mitad de
        un mes de pago, esa cuota es en proporción a los días que vive ahí. Con `fin`, cómo quedarían si el contrato
        terminara ese día (si no, hasta su fecha de fin)."""
        valores = []
        for contrato in self.filtered(lambda c: c.estado == 'vigente'):
            fecha_fin = fin or contrato.fecha_fin
            existentes = set(contrato.cuota_ids.mapped('periodo'))
            # Desde el mes de pago en que empieza (el del mes anterior, si empieza antes del día de pago), pero nunca
            # uno anterior a la primera cuota que ya tiene.
            mes = contrato._mes_del_dia(contrato.fecha_inicio)
            if existentes:
                mes = max(mes, min(existentes))
            while True:
                primer_dia, ultimo_dia = contrato._periodo(mes)
                vence = max(primer_dia, contrato.fecha_inicio)
                if vence > hasta or (fecha_fin and vence > fecha_fin):
                    break
                if mes not in existentes:
                    dias = ((min(ultimo_dia, fecha_fin) if fecha_fin else ultimo_dia) - vence).days + 1
                    dias_periodo = (ultimo_dia - primer_dia).days + 1
                    valores.append({
                        'contrato_id': contrato.id,
                        'periodo': mes,
                        'fecha_vencimiento': vence,
                        'monto': round(contrato._monto_para(vence) * dias / dias_periodo),
                        'dias': dias,
                        'dias_periodo': dias_periodo,
                    })
                mes += relativedelta(months=1)
        return valores

    def _cuota_hasta(self, cuota, fin, fin_anterior):
        """Días y monto de `cuota` si el contrato termina el día `fin` (vacío: sin fin) en vez de `fin_anterior`.
        Si le tocan menos días, la proporción de lo que cobraba (sin bajar de lo que ya se pagó de alquiler); si le
        tocan más (renovación), los días que se agregan van con el alquiler que rige desde el día siguiente a
        `fin_anterior`: así no se cobran dos veces los mismos días."""
        self.ensure_one()
        primer_dia, ultimo_dia = self._periodo(cuota.periodo)
        dias_periodo = cuota.dias_periodo or (ultimo_dia - primer_dia).days + 1
        antes = cuota.dias or dias_periodo
        dias = ((min(ultimo_dia, fin) if fin else ultimo_dia) - max(primer_dia, self.fecha_inicio)).days + 1
        monto = cuota.monto
        if dias < antes:
            monto = max(round(cuota.monto * dias / antes), cuota.pagado - cuota.cargos)
        elif dias > antes:
            alquiler = self._monto_para(fin_anterior + timedelta(days=1))
            monto += round(alquiler * (dias - antes) / dias_periodo)
        return {'dias': dias, 'dias_periodo': dias_periodo, 'monto': monto}

    def _ajustar_cuota_del_fin(self, anterior):
        """Después de cambiar la fecha de fin (al terminar o renovar), la cuota del mes de pago en que terminaba o
        termina ahora se cobra por los días que le tocan (ver _cuota_hasta)."""
        self.ensure_one()
        limites = [fecha for fecha in (anterior, self.fecha_fin) if fecha]
        if anterior == self.fecha_fin or not limites:
            return
        mes = self._mes_del_dia(min(limites))
        for cuota in self.cuota_ids.filtered(lambda c: c.periodo == mes):
            valores = self._cuota_hasta(cuota, self.fecha_fin, anterior)
            if any(cuota[campo] != valor for campo, valor in valores.items()):
                cuota.write(valores)

    def _aplicar_reajustes(self, hoy=None):
        """Cambia el alquiler de los contratos que llegaron al día en que empieza la renovación con un alquiler
        nuevo o a su fecha de reajuste."""
        hoy = hoy or fields.Date.context_today(self)
        for contrato in self.filtered(lambda c: c.estado == 'vigente'):
            if contrato.fecha_renovacion and contrato.fecha_renovacion <= hoy:
                anterior = contrato.monto
                contrato.write({'monto': contrato.monto_renovacion, 'monto_renovacion': 0, 'fecha_renovacion': False})
                contrato.message_post(body=(
                    f'Empieza la renovación: el alquiler pasa de {guaranies(anterior)} a {guaranies(contrato.monto)}.'))
            while contrato.reajuste_pct and contrato.fecha_reajuste and contrato.fecha_reajuste <= hoy:
                anterior = contrato.monto
                contrato.write({
                    'monto': contrato.monto_reajustado,
                    'fecha_reajuste': contrato.fecha_reajuste + relativedelta(years=1),
                })
                contrato.message_post(body=(
                    f'Reajuste anual del {contrato.reajuste_pct:g} %: el alquiler pasa de {guaranies(anterior)} '
                    f'a {guaranies(contrato.monto)}.'))

    @api.model
    def _cron_generar_cuotas(self):
        hoy = fields.Date.context_today(self)
        vigentes = self.search([('estado', '=', 'vigente')])
        vigentes._aplicar_reajustes(hoy)
        # Los que se terminaron con un día de salida que ya pasó: se terminan del todo y se liquida el depósito.
        se_fueron = vigentes.filtered(lambda c: c.fecha_salida and c.fecha_salida < hoy)
        for contrato in se_fueron:
            contrato._terminar(contrato.fecha_salida, contrato.deposito_descuento, contrato.deposito_motivo)
        (vigentes - se_fueron)._generar_cuotas()

    def _cuota_para_cargos(self):
        """La cuota a la que se suman los cargos extra (ANDE, agua, reparaciones): la próxima sin pagar o, si no
        hay, la última."""
        self.ensure_one()
        hoy = fields.Date.context_today(self)
        pendientes = self.cuota_ids.filtered(lambda c: c.estado != 'pagada').sorted('fecha_vencimiento')
        proximas = pendientes.filtered(lambda c: c.fecha_vencimiento >= hoy)
        return proximas[:1] or pendientes[:1] or self.cuota_ids.sorted('fecha_vencimiento')[-1:]

    # Avisos por WhatsApp sobre el contrato
    def _whatsapp(self, texto):
        self.ensure_one()
        codigo_pais = str(self.company_id.country_id.phone_code or 595)
        numero = numero_whatsapp(self.inquilino_id.mobile or self.inquilino_id.phone, codigo_pais)
        if not numero:
            raise UserError(f'{self.inquilino_id.name} no tiene teléfono cargado.')
        self.message_post(body=f'Aviso por WhatsApp: {texto}')
        return {'type': 'ir.actions.act_url', 'url': f'https://wa.me/{numero}?text={quote(texto)}', 'target': 'new'}

    def _texto_vencimiento(self):
        return (f'¡Hola {primer_nombre(self.inquilino_id.name)}! Te recordamos que tu contrato de alquiler de '
                f'{self.unidad_id.display_name} vence el {fecha_larga(self.fecha_fin)}. ¿Querés renovarlo? '
                'Avisanos por acá. ¡Gracias!')

    def _texto_reajuste(self):
        return (f'¡Hola {primer_nombre(self.inquilino_id.name)}! Te avisamos que desde el '
                f'{fecha_corta(self.fecha_reajuste)} el alquiler de {self.unidad_id.display_name} pasa de '
                f'{guaranies(self.monto)} a {guaranies(self.monto_reajustado)} (reajuste anual del '
                f'{self.reajuste_pct:g} %, como dice el contrato). ¡Gracias!')

    def action_avisar_vencimiento(self):
        self.ensure_one()
        if not self.fecha_fin:
            raise UserError('El contrato no tiene fecha de fin.')
        return self._whatsapp(self._texto_vencimiento())

    def action_avisar_reajuste(self):
        self.ensure_one()
        if not (self.reajuste_pct and self.fecha_reajuste):
            raise UserError('El contrato no tiene reajuste anual.')
        return self._whatsapp(self._texto_reajuste())

    # Contrato impreso
    def _parte_locadora(self):
        return self.propiedad_id.propietario_id or self.company_id.partner_id

    def _clausulas(self):
        """Las cláusulas del contrato impreso, como (título, texto). Es un modelo: conviene que lo revise un
        abogado antes de usarlo."""
        self.ensure_one()
        unidad = self.unidad_id
        propiedad = self.propiedad_id
        lugar = ', '.join(parte for parte in (propiedad.direccion, propiedad.ciudad) if parte)
        clausulas = [
            ('Objeto', f'EL LOCADOR da en alquiler a EL LOCATARIO el inmueble {unidad.display_name}, ubicado en '
                       f'{lugar}, que se destinará exclusivamente a vivienda de EL LOCATARIO y su familia.'),
            ('Plazo', f'El alquiler empieza el {fecha_larga(self.fecha_inicio)} y termina el '
                      f'{fecha_larga(self.fecha_fin)}.' if self.fecha_fin else
                      f'El alquiler empieza el {fecha_larga(self.fecha_inicio)}, por tiempo indeterminado.'),
            ('Precio y forma de pago', f'El alquiler mensual es de {en_letras(self.monto)} ({guaranies(self.monto)}), '
                                       f'que EL LOCATARIO pagará por adelantado hasta el día {self.dia_pago} de cada '
                                       'mes, por el mes que va desde ese día hasta el día anterior del mes siguiente. '
                                       'Si el alquiler empieza o termina a mitad de uno de esos meses, ese mes se paga '
                                       'en proporción a los días. Cada pago se acredita con el recibo '
                                       'correspondiente.'),
        ]
        if self.reajuste_pct:
            clausulas.append(('Reajuste', f'El alquiler se reajustará cada año un {self.reajuste_pct:g} %, a partir '
                                          f'del {fecha_larga(self.fecha_reajuste)}.'))
        if self.deposito:
            clausulas.append(('Depósito de garantía', f'EL LOCATARIO entrega {en_letras(self.deposito)} '
                                                      f'({guaranies(self.deposito)}) en garantía. Al terminar el '
                                                      'contrato se le devuelve, descontando lo que deba y el arreglo '
                                                      'de los daños que no sean por el uso normal.'))
        clausulas += [
            ('Servicios', 'Los consumos de ANDE, agua y demás servicios del inmueble durante el alquiler están a '
                          'cargo de EL LOCATARIO.'),
            ('Cuidado del inmueble', 'EL LOCATARIO recibe el inmueble en el estado que consta en el acta de entrega '
                                     'y se compromete a cuidarlo y devolverlo en el mismo estado. No puede hacer '
                                     'cambios ni obras sin permiso por escrito de EL LOCADOR.'),
            ('Subalquiler', 'EL LOCATARIO no puede subalquilar ni ceder el inmueble, en todo o en parte.'),
            ('Falta de pago', 'La falta de pago de dos meses seguidos permite a EL LOCADOR dar por terminado el '
                              'contrato y pedir la devolución del inmueble.'),
        ]
        if self.garante_id:
            clausulas.append(('Garantía', f'{self.garante_id.name} se constituye en garante solidario de todas las '
                                          'obligaciones de EL LOCATARIO en este contrato.'))
        if self.clausulas_extra:
            clausulas.append(('Cláusulas adicionales', self.clausulas_extra))
        return clausulas

    def _ordinal(self, numero):
        ordinales = ['primera', 'segunda', 'tercera', 'cuarta', 'quinta', 'sexta', 'séptima', 'octava', 'novena',
                     'décima', 'undécima', 'duodécima', 'decimotercera', 'decimocuarta', 'decimoquinta']
        return ordinales[numero - 1].upper() if numero <= len(ordinales) else str(numero)

    def _fecha_texto(self, fecha):
        return fecha_larga(fecha)

    def action_ver_cuotas(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('alquileres.action_alquiler_cuota')
        action['domain'] = [('contrato_id', '=', self.id)]
        action['context'] = {}
        return action

    def action_ver_pagos(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('alquileres.action_alquiler_pago')
        action['domain'] = [('contrato_id', '=', self.id)]
        action['context'] = {}
        return action

    def action_ver_actas(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('alquileres.action_alquiler_acta')
        action['domain'] = [('contrato_id', '=', self.id)]
        action['context'] = {'default_contrato_id': self.id}
        return action

    def action_nueva_acta(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Acta de entrega',
            'res_model': 'alquiler.acta',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'context': {'default_contrato_id': self.id,
                        'default_tipo': 'salida' if self.estado == 'terminado' else 'entrada'},
        }
