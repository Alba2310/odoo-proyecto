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
    fecha_inicio = fields.Date('Desde', required=True, default=fields.Date.context_today, tracking=True)
    fecha_fin = fields.Date('Hasta', tracking=True, help='Vacío si el contrato no tiene fecha de fin.')
    monto = fields.Monetary('Alquiler mensual', required=True, tracking=True,
                            help='Si cambia (reajuste), las cuotas que se crean desde ahí usan el monto nuevo.')
    dia_pago = fields.Integer('Día de pago', compute='_compute_dia_pago', store=True, readonly=False,
                              precompute=True, tracking=True,
                              help='Día de cada mes en que vence el alquiler. Si el mes es más corto, vence el último '
                                   'día. Se propone el mismo día en que empieza el contrato.')
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
        for contrato in self:
            contrato.dia_pago = contrato.fecha_inicio.day if contrato.fecha_inicio else 1

    @api.depends('fecha_inicio', 'reajuste_pct')
    def _compute_fecha_reajuste(self):
        # Se propone al año de empezar; si ya tiene una fecha (porque se cargó o ya hubo reajustes), se respeta.
        for contrato in self:
            if not contrato.reajuste_pct:
                contrato.fecha_reajuste = False
            elif not contrato.fecha_reajuste and contrato.fecha_inicio:
                contrato.fecha_reajuste = contrato.fecha_inicio + relativedelta(years=1)
            else:
                contrato.fecha_reajuste = contrato.fecha_reajuste

    @api.depends('monto', 'reajuste_pct')
    def _compute_monto_reajustado(self):
        for contrato in self:
            contrato.monto_reajustado = round(contrato.monto * (1 + contrato.reajuste_pct / 100), -3)

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

    @api.depends('estado', 'fecha_fin', 'fecha_reajuste')
    def _compute_avisos_contrato(self):
        hoy = fields.Date.context_today(self)
        for contrato in self:
            vigente = contrato.estado == 'vigente'
            contrato.vence_pronto = bool(vigente and contrato.fecha_fin
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
        for contrato in self:
            if contrato.estado != 'borrador':
                raise UserError(f'El contrato {contrato.name} ya se activó.')
        self.write({'estado': 'vigente'})
        self._generar_cuotas()
        return True

    def action_terminar(self):
        """Abre la ventana para terminar el contrato y liquidar el depósito."""
        self.ensure_one()
        if self.estado != 'vigente':
            raise UserError(f'Solo se puede terminar un contrato vigente ({self.name}).')
        return {
            'type': 'ir.actions.act_window',
            'name': f'Terminar contrato {self.name}',
            'res_model': 'alquiler.terminar.wizard',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {'default_contrato_id': self.id},
        }

    def _terminar(self, fecha=None, descuento=0, motivo=False):
        """Termina el contrato el día `fecha` (hoy si no se dice): la unidad queda libre, se borran las cuotas sin
        pagar que vencen después y el depósito paga lo que quedó debiendo. `descuento` es lo que se descuenta del
        depósito por daños."""
        fecha = fecha or fields.Date.context_today(self)
        for contrato in self:
            if contrato.estado != 'vigente':
                raise UserError(f'Solo se puede terminar un contrato vigente ({contrato.name}).')
            fin = max(min(contrato.fecha_fin or fecha, fecha), contrato.fecha_inicio)
            contrato.write({'estado': 'terminado', 'fecha_fin': fin})
            contrato.cuota_ids.filtered(lambda c: c.fecha_vencimiento > fin and not c.pago_ids).unlink()
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

    def _monto_para(self, vence):
        """Alquiler de la cuota que vence en `vence`: si ya llegó la fecha de reajuste, el monto reajustado."""
        self.ensure_one()
        if self.reajuste_pct and self.fecha_reajuste and vence >= self.fecha_reajuste:
            return self.monto_reajustado
        return self.monto

    def _generar_cuotas(self, hasta=None):
        """Crea las cuotas que faltan de los contratos vigentes, hasta las que vencen en la fecha `hasta`
        (por defecto, en los próximos días). Cada cuota vence el día de pago de su mes; la del primer mes, si ese
        día ya pasó cuando empieza el contrato, vence el día que empieza."""
        hasta = hasta or fields.Date.context_today(self) + timedelta(days=DIAS_ANTICIPACION)
        valores = []
        for contrato in self.filtered(lambda c: c.estado == 'vigente'):
            existentes = set(contrato.cuota_ids.mapped('periodo'))
            mes = contrato.fecha_inicio.replace(day=1)
            while True:
                vence = max(vencimiento_del_mes(mes, contrato.dia_pago), contrato.fecha_inicio)
                if vence > hasta or (contrato.fecha_fin and vence > contrato.fecha_fin):
                    break
                if mes not in existentes:
                    valores.append({
                        'contrato_id': contrato.id,
                        'periodo': mes,
                        'fecha_vencimiento': vence,
                        'monto': contrato._monto_para(vence),
                    })
                mes += relativedelta(months=1)
        return self.env['alquiler.cuota'].create(valores)

    def _aplicar_reajustes(self, hoy=None):
        """Sube el alquiler de los contratos que llegaron a su fecha de reajuste."""
        hoy = hoy or fields.Date.context_today(self)
        for contrato in self.filtered(lambda c: c.estado == 'vigente' and c.reajuste_pct and c.fecha_reajuste):
            while contrato.fecha_reajuste <= hoy:
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
        vigentes = self.search([('estado', '=', 'vigente')])
        vigentes._aplicar_reajustes()
        vigentes._generar_cuotas()

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
                                       'mes. Cada pago se acredita con el recibo correspondiente.'),
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
