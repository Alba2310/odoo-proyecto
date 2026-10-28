# -*- coding: utf-8 -*-
from urllib.parse import quote

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .utiles import en_letras, fecha_larga, guaranies, mes_y_anio, numero_whatsapp, primer_nombre

MEDIOS_PAGO = [
    ('efectivo', 'Efectivo'),
    ('transferencia', 'Transferencia'),
    ('billetera', 'Billetera (Tigo Money, Personal...)'),
    ('deposito', 'Del depósito de garantía'),
    ('otro', 'Otro'),
]


class AlquilerPago(models.Model):
    """Un pago, total o parcial, de una cuota. Cada pago tiene su recibo numerado."""
    _name = 'alquiler.pago'
    _description = 'Pago de alquiler'
    _order = 'fecha desc, id desc'

    name = fields.Char('Recibo N°', readonly=True, copy=False, default='Nuevo')
    cuota_id = fields.Many2one('alquiler.cuota', string='Cuota', required=True, ondelete='restrict', index=True,
                               domain=[('estado', '!=', 'pagada')])
    mes = fields.Char(related='cuota_id.name', string='Mes')
    contrato_id = fields.Many2one(related='cuota_id.contrato_id', store=True, string='Contrato')
    inquilino_id = fields.Many2one(related='cuota_id.inquilino_id', store=True, string='Inquilino')
    unidad_id = fields.Many2one(related='cuota_id.unidad_id', store=True, string='Unidad')
    propiedad_id = fields.Many2one(related='cuota_id.propiedad_id', store=True, string='Propiedad')
    company_id = fields.Many2one(related='cuota_id.company_id', store=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    fecha = fields.Date('Fecha', required=True, default=fields.Date.context_today)
    monto = fields.Monetary('Monto', required=True)
    medio = fields.Selection(MEDIOS_PAGO, string='Medio de pago', required=True, default='efectivo')
    comprobante = fields.Binary('Comprobante', attachment=True, help='Foto o PDF de la transferencia.')
    comprobante_nombre = fields.Char('Nombre del comprobante')
    nota = fields.Char('Nota')
    saldo_cuota = fields.Monetary(related='cuota_id.saldo', string='Falta pagar de la cuota')
    whatsapp_url = fields.Char('Enlace de WhatsApp', compute='_compute_whatsapp_url')

    _sql_constraints = [
        ('monto_positivo', 'CHECK(monto > 0)', 'El monto del pago tiene que ser mayor a cero.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code('alquiler.pago') or 'Nuevo'
        return super().create(vals_list)

    @api.onchange('cuota_id')
    def _onchange_cuota_id(self):
        if self.cuota_id and not self.monto:
            self.monto = self.cuota_id.saldo

    @api.constrains('monto', 'cuota_id')
    def _check_no_supera_la_cuota(self):
        for pago in self:
            cuota = pago.cuota_id
            if pago.currency_id.compare_amounts(cuota.saldo, 0) < 0:
                raise ValidationError(
                    f'El pago supera lo que falta pagar de {cuota.name} '
                    f'({guaranies(cuota.saldo + pago.monto)}).')

    def _saldo_despues(self):
        """Lo que faltaba pagar de la cuota justo después de este pago (para el recibo)."""
        self.ensure_one()
        anteriores = self.cuota_id.pago_ids.filtered(lambda p: (p.fecha, p.id) <= (self.fecha, self.id))
        return self.cuota_id.total - sum(anteriores.mapped('monto'))

    def _detalle_cuota(self):
        """Lo que se cobró en la cuota, si además del alquiler tiene cargos extra (para el recibo)."""
        self.ensure_one()
        return self.cuota_id._detalle() if self.cuota_id.cargo_ids else ''

    def _saldo_despues_texto(self):
        return guaranies(self._saldo_despues())

    def _monto_en_letras(self):
        return en_letras(self.monto)

    def _monto_texto(self):
        return guaranies(self.monto)

    def _fecha_texto(self):
        return fecha_larga(self.fecha)

    def _mes_texto(self):
        return mes_y_anio(self.cuota_id.periodo)

    def _firma(self):
        return self.propiedad_id.propietario_id.name or self.company_id.name

    def _texto_whatsapp(self):
        self.ensure_one()
        texto = (f'¡Hola {primer_nombre(self.inquilino_id.name)}! Recibimos tu pago de {guaranies(self.monto)} '
                 f'del alquiler de {self._mes_texto()} ({self.unidad_id.display_name}). Recibo N° {self.name}.')
        saldo = self._saldo_despues()
        if saldo > 0:
            texto += f' Queda pendiente {guaranies(saldo)}.'
        return texto + ' ¡Muchas gracias!'

    @api.depends('inquilino_id.phone', 'inquilino_id.mobile', 'monto', 'name')
    def _compute_whatsapp_url(self):
        for pago in self:
            codigo_pais = str(pago.company_id.country_id.phone_code or 595)
            numero = numero_whatsapp(pago.inquilino_id.mobile or pago.inquilino_id.phone, codigo_pais)
            if numero and pago.id:
                pago.whatsapp_url = f'https://wa.me/{numero}?text={quote(pago._texto_whatsapp())}'
            else:
                pago.whatsapp_url = False

    def action_whatsapp(self):
        """Abre WhatsApp con la confirmación del pago escrita, para que el inquilino sepa que se registró."""
        self.ensure_one()
        if not self.whatsapp_url:
            raise UserError(f'{self.inquilino_id.name} no tiene teléfono cargado.')
        return {'type': 'ir.actions.act_url', 'url': self.whatsapp_url, 'target': 'new'}
