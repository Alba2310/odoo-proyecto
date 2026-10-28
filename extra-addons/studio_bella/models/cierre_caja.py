# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_amount

ESTADOS_CAJA = [
    ('abierta', 'Abierta'),
    ('cerrada', 'Cerrada'),
]
RESULTADOS_ARQUEO = [
    ('cuadra', 'Cuadra'),
    ('sobra', 'Sobra'),
    ('falta', 'Falta'),
]
# Lo que se puede seguir cambiando con la caja cerrada.
CAMPOS_CAJA_CERRADA = {'estado', 'nota'}


class BellaCierreCaja(models.Model):
    """Cierre de caja del día: lo cobrado con cada forma de pago y el arqueo del efectivo.

    Los totales salen de las citas y ventas cobradas ese día (la fecha de su factura) y se actualizan solos con
    cada cobro. Con la caja cerrada no se puede cobrar con fecha de ese día.
    """
    _name = 'bella.cierre.caja'
    _description = 'Cierre de caja'
    _inherit = ['mail.thread']
    _order = 'fecha desc, id desc'
    _check_company_auto = True

    name = fields.Char('Nombre', compute='_compute_name', store=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                 default=lambda self: self.env.company)
    fecha = fields.Date('Día', required=True, default=fields.Date.context_today, tracking=True)
    responsable_id = fields.Many2one('res.users', string='Responsable', default=lambda self: self.env.user,
                                     tracking=True)
    estado = fields.Selection(ESTADOS_CAJA, string='Estado', default='abierta', required=True, readonly=True,
                              tracking=True, copy=False)
    currency_id = fields.Many2one(related='company_id.currency_id')

    # Lo cobrado en el día
    cita_ids = fields.Many2many('bella.cita', string='Citas cobradas', compute='_compute_cobros')
    venta_ids = fields.Many2many('bella.venta', string='Ventas cobradas', compute='_compute_cobros')
    cantidad_cobros = fields.Integer('Cobros', compute='_compute_totales', store=True)
    total_efectivo = fields.Monetary('Efectivo', compute='_compute_totales', store=True)
    total_tarjeta = fields.Monetary('Tarjeta', compute='_compute_totales', store=True)
    total_transferencia = fields.Monetary('Transferencia / QR', compute='_compute_totales', store=True)
    total_cobrado = fields.Monetary('Total cobrado', compute='_compute_totales', store=True)

    # Arqueo del efectivo
    fondo_inicial = fields.Monetary('Cambio al abrir', default=lambda self: self._default_fondo_inicial(),
                                    tracking=True, help='Efectivo que había en la caja al empezar el día.')
    retiros = fields.Monetary('Salidas de efectivo', tracking=True,
                              help='Efectivo que se sacó de la caja durante el día: compras chicas, pagos, '
                                   'depósitos al banco.')
    efectivo_esperado = fields.Monetary('Tiene que haber', compute='_compute_arqueo', store=True,
                                        help='Cambio al abrir + cobrado en efectivo - salidas de efectivo.')
    efectivo_contado = fields.Monetary('Efectivo contado', tracking=True,
                                       help='Lo que hay en la caja al cerrar, contado billete por billete.')
    diferencia = fields.Monetary('Diferencia', compute='_compute_arqueo', store=True,
                                 help='Positiva: sobra plata. Negativa: falta.')
    resultado = fields.Selection(RESULTADOS_ARQUEO, string='Resultado', compute='_compute_arqueo', store=True)
    resultado_texto = fields.Char('Resultado del arqueo', compute='_compute_resultado_texto')
    queda_en_caja = fields.Monetary('Queda de cambio', compute='_compute_queda_en_caja', store=True, readonly=False,
                                    precompute=True, tracking=True,
                                    help='Efectivo que se deja en la caja para dar cambio al día siguiente.')
    para_retirar = fields.Monetary('Para retirar', compute='_compute_arqueo', store=True,
                                   help='Efectivo contado menos lo que queda de cambio.')
    nota = fields.Text('Notas')

    _sql_constraints = [
        ('dia_unico', 'unique(company_id, fecha)', 'Ya hay un cierre de caja para ese día.'),
    ]

    @api.model
    def _default_fondo_inicial(self):
        # Lo que quedó de cambio en el último cierre.
        anterior = self.search([('company_id', '=', self.env.company.id)], order='fecha desc', limit=1)
        return anterior.queda_en_caja

    def write(self, vals):
        if set(vals) - CAMPOS_CAJA_CERRADA and any(cierre.estado == 'cerrada' for cierre in self):
            raise UserError('La caja está cerrada: para corregirla, primero hay que reabrirla.')
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_excepto_cerradas(self):
        if any(cierre.estado == 'cerrada' for cierre in self):
            raise UserError('No se puede eliminar una caja cerrada.')

    # Campos calculados

    @api.depends('fecha')
    def _compute_name(self):
        for cierre in self:
            cierre.name = f'Caja del {cierre.fecha.strftime("%d/%m/%Y")}' if cierre.fecha else 'Cierre de caja'

    def _cobros_del_dia(self):
        """Citas y ventas cobradas ese día, según la fecha de su factura (solo las cobradas tienen factura)."""
        self.ensure_one()
        if not self.fecha:
            return self.env['bella.cita'], self.env['bella.venta']
        dominio = [
            ('company_id', '=', self.company_id.id),
            ('factura_id.invoice_date', '=', self.fecha),
        ]
        return (self.env['bella.cita'].search(dominio, order='fecha_inicio'),
                self.env['bella.venta'].search(dominio, order='fecha'))

    @api.depends('fecha', 'company_id')
    def _compute_cobros(self):
        for cierre in self:
            cierre.cita_ids, cierre.venta_ids = cierre._cobros_del_dia()

    @api.depends('fecha', 'company_id')
    def _compute_totales(self):
        for cierre in self:
            citas, ventas = cierre._cobros_del_dia()
            totales = {'efectivo': 0, 'tarjeta': 0, 'transferencia': 0}
            for documento in list(citas) + list(ventas):
                totales[documento.metodo_pago] += documento.factura_id.amount_total
            cierre.cantidad_cobros = len(citas) + len(ventas)
            cierre.total_efectivo = totales['efectivo']
            cierre.total_tarjeta = totales['tarjeta']
            cierre.total_transferencia = totales['transferencia']
            cierre.total_cobrado = sum(totales.values())

    @api.depends('fondo_inicial')
    def _compute_queda_en_caja(self):
        # Lo de siempre es dejar el mismo cambio con el que se abrió.
        for cierre in self:
            cierre.queda_en_caja = cierre.fondo_inicial

    @api.depends('fondo_inicial', 'total_efectivo', 'retiros', 'efectivo_contado', 'queda_en_caja')
    def _compute_arqueo(self):
        for cierre in self:
            cierre.efectivo_esperado = cierre.fondo_inicial + cierre.total_efectivo - cierre.retiros
            cierre.diferencia = cierre.efectivo_contado - cierre.efectivo_esperado
            cierre.para_retirar = cierre.efectivo_contado - cierre.queda_en_caja
            comparacion = cierre.currency_id.compare_amounts(cierre.diferencia, 0) if cierre.currency_id else 0
            cierre.resultado = 'sobra' if comparacion > 0 else 'falta' if comparacion < 0 else 'cuadra'

    @api.depends('resultado', 'diferencia', 'efectivo_contado')
    def _compute_resultado_texto(self):
        for cierre in self:
            monto = format_amount(self.env, abs(cierre.diferencia), cierre.currency_id) if cierre.currency_id else ''
            if cierre.resultado == 'sobra':
                cierre.resultado_texto = f'Sobran {monto}'
            elif cierre.resultado == 'falta':
                cierre.resultado_texto = f'Faltan {monto}'
            else:
                cierre.resultado_texto = 'La caja cuadra justo'

    # Cobros

    @api.model
    def _verificar_caja_abierta(self, company, fecha):
        """Con la caja de un día cerrada, no se puede cobrar con esa fecha."""
        cerrada = self.sudo().search([
            ('company_id', '=', company.id), ('fecha', '=', fecha), ('estado', '=', 'cerrada'),
        ], limit=1)
        if cerrada:
            raise UserError(f'La {cerrada.name.lower()} ya está cerrada. Para cobrar con esa fecha, '
                            'alguien de Administración tiene que reabrirla.')

    @api.model
    def _actualizar_dia(self, company, fecha):
        """Un cobro nuevo suma en el cierre de caja de ese día, si ya se empezó."""
        cierres = self.sudo().search([
            ('company_id', '=', company.id), ('fecha', '=', fecha), ('estado', '=', 'abierta'),
        ])
        cierres.modified(['fecha'])

    # Botones

    def action_cerrar(self):
        for cierre in self:
            if cierre.estado != 'abierta':
                raise UserError(f'La {cierre.name.lower()} ya está cerrada.')
            if cierre.fecha > fields.Date.context_today(cierre):
                raise UserError('No se puede cerrar la caja de un día que todavía no llegó.')
            moneda = cierre.currency_id
            if not moneda.is_zero(cierre.efectivo_esperado) and moneda.is_zero(cierre.efectivo_contado):
                raise UserError('Cuente el efectivo de la caja y cárguelo en "Efectivo contado" antes de cerrar.')
            if moneda.compare_amounts(cierre.queda_en_caja, cierre.efectivo_contado) > 0:
                raise UserError('No puede quedar de cambio más efectivo del que se contó.')
            cierre.write({'estado': 'cerrada', 'responsable_id': self.env.user.id})
            if cierre.resultado != 'cuadra':
                cierre.message_post(body=Markup('Caja cerrada: <b>%s</b>.') % cierre.resultado_texto)
        return True

    def action_reabrir(self):
        if not self.env.user.has_group('studio_bella.group_bella_admin'):
            raise UserError('Solo Administración puede reabrir una caja cerrada.')
        self.write({'estado': 'abierta'})
        # Por si se cobró algo con esa fecha mientras estaba cerrada (por ejemplo, desde Facturación).
        self.modified(['fecha'])
        return True
