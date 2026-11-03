# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import fields, models
from odoo.exceptions import UserError

from .account_move_line import DOMINIO_CUENTA_CORRIENTE

GRUPOS_FACTURACION = 'account.group_account_invoice,account.group_account_readonly'


class ResPartner(models.Model):
    _inherit = 'res.partner'

    moneda_usd_id = fields.Many2one('res.currency', compute='_compute_moneda_usd_id')
    saldo_gs = fields.Monetary(
        'Saldo Gs', currency_field='currency_id', compute='_compute_saldos', groups=GRUPOS_FACTURACION,
        help='Lo que debe el cliente en guaraníes: el Debe menos el Haber de su cuenta corriente. '
             'Si es negativo, tiene saldo a favor.')
    saldo_usd = fields.Monetary(
        'Saldo USD', currency_field='moneda_usd_id', compute='_compute_saldos', groups=GRUPOS_FACTURACION,
        help='Lo mismo en dólares.')
    con_saldo = fields.Boolean(
        'Con saldo pendiente', compute='_compute_saldos', search='_search_con_saldo', groups=GRUPOS_FACTURACION)

    def _compute_moneda_usd_id(self):
        self.moneda_usd_id = self.env.ref('base.USD')

    def _saldos_cuenta_corriente(self, dominio):
        """{cliente: (saldo Gs, saldo USD)} de los movimientos del dominio. Los movimientos de los contactos de una
        empresa se suman a la empresa (commercial_partner_id)."""
        saldos = defaultdict(lambda: [0.0, 0.0])
        for socio, debe, haber, debe_usd, haber_usd in self.env['account.move.line']._read_group(
                [*dominio, *DOMINIO_CUENTA_CORRIENTE], ['partner_id'],
                ['debit:sum', 'credit:sum', 'debe_usd:sum', 'haber_usd:sum']):
            saldo = saldos[socio.commercial_partner_id]
            saldo[0] += debe - haber
            saldo[1] += debe_usd - haber_usd
        return saldos

    def _compute_saldos(self):
        clientes = self.commercial_partner_id._origin
        saldos = self._saldos_cuenta_corriente([('partner_id', 'child_of', clientes.ids)]) if clientes else {}
        for partner in self:
            saldo_gs, saldo_usd = saldos.get(partner.commercial_partner_id._origin, (0.0, 0.0))
            partner.saldo_gs = saldo_gs
            partner.saldo_usd = round(saldo_usd, 2)
            partner.con_saldo = not partner.currency_id.is_zero(saldo_gs)

    def _search_con_saldo(self, operator, value):
        if operator not in ('=', '!='):
            raise UserError('Solo se puede buscar si el cliente tiene o no saldo pendiente.')
        moneda = self.env.company.currency_id
        ids = [cliente.id for cliente, (saldo_gs, _usd) in self._saldos_cuenta_corriente([]).items()
               if not moneda.is_zero(saldo_gs)]
        return [('commercial_partner_id', 'in' if (operator == '=') == bool(value) else 'not in', ids)]

    def action_ver_cuenta_corriente(self):
        self.ensure_one()
        accion = self.env['ir.actions.act_window']._for_xml_id('cuenta_corriente.action_cuenta_corriente')
        accion['context'] = {'search_default_partner_id': self.commercial_partner_id.id}
        return accion

    def action_extracto(self):
        self.ensure_one()
        accion = self.env['ir.actions.act_window']._for_xml_id('cuenta_corriente.action_extracto')
        accion['context'] = {'default_partner_id': self.commercial_partner_id.id}
        return accion

    def _extracto_cuenta_corriente(self, desde, hasta):
        """Lo que va en el extracto en PDF: los movimientos del período (cada uno con el saldo que quedó después),
        el saldo con que empezó el período y los totales."""
        self.ensure_one()
        cliente = self.commercial_partner_id
        dominio = [('partner_id', 'child_of', cliente.id), ('date', '<=', hasta), *DOMINIO_CUENTA_CORRIENTE]
        anterior_gs = anterior_usd = 0.0
        if desde:
            dominio.append(('date', '>=', desde))
            anterior = self._saldos_cuenta_corriente([('partner_id', 'child_of', cliente.id), ('date', '<', desde)])
            anterior_gs, anterior_usd = anterior.get(cliente, (0.0, 0.0))
        movimientos = self.env['account.move.line'].search(dominio, order='date, id')
        totales = {campo: sum(movimientos.mapped(campo)) for campo in ('debit', 'credit', 'debe_usd', 'haber_usd')}
        return {
            'movimientos': movimientos,
            'anterior_gs': anterior_gs,
            'anterior_usd': round(anterior_usd, 2),
            **totales,
            'saldo_gs': anterior_gs + totales['debit'] - totales['credit'],
            'saldo_usd': round(anterior_usd + totales['debe_usd'] - totales['haber_usd'], 2),
        }
