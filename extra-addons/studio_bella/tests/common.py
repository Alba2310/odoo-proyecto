# -*- coding: utf-8 -*-
from datetime import datetime

from odoo import Command
from odoo.tests import Form

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


class StudioBellaCommon(AccountTestInvoicingCommon):
    """Servicios, productos con stock, un estilista con el horario de la peluquería y un cliente."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.groups_id += cls.env.ref('studio_bella.group_bella_admin')
        cls.company = cls.env.company
        cls.warehouse = cls.env['stock.warehouse'].search([('company_id', '=', cls.company.id)], limit=1)
        cls.stock = cls.warehouse.lot_stock_id

        # IVA 10 % incluido en el precio, como en Paraguay.
        cls.iva_10 = cls.env['account.tax'].create({
            'name': 'IVA 10 % de prueba',
            'amount': 10,
            'type_tax_use': 'sale',
            'price_include_override': 'tax_included',
        })
        categoria_servicios = cls.env.ref('studio_bella.categoria_servicios')
        categoria_productos = cls.env.ref('studio_bella.categoria_productos')

        cls.tinte = cls.env['product.product'].create({
            'name': 'Tinte de prueba', 'type': 'consu', 'is_storable': True, 'sale_ok': False,
            'categ_id': categoria_productos.id,
        })
        cls.shampoo = cls.env['product.product'].create({
            'name': 'Shampoo de prueba', 'type': 'consu', 'is_storable': True, 'list_price': 50,
            'categ_id': categoria_productos.id, 'taxes_id': [Command.set(cls.iva_10.ids)],
        })
        cls.corte = cls.env['product.product'].create({
            'name': 'Corte de prueba', 'type': 'service', 'list_price': 100, 'bella_duracion': 60,
            'categ_id': categoria_servicios.id, 'taxes_id': [Command.set(cls.iva_10.ids)],
        })
        cls.color = cls.env['product.product'].create({
            'name': 'Color de prueba', 'type': 'service', 'list_price': 200, 'bella_duracion': 90,
            'categ_id': categoria_servicios.id, 'taxes_id': [Command.set(cls.iva_10.ids)],
            'bella_insumo_ids': [Command.create({'producto_id': cls.tinte.id, 'cantidad': 1})],
        })
        cls.manicura = cls.env['product.product'].create({
            'name': 'Manicura de prueba', 'type': 'service', 'list_price': 40, 'bella_duracion': 45,
            'categ_id': categoria_servicios.id,
        })
        cls.env['stock.quant']._update_available_quantity(cls.shampoo, cls.stock, 5)
        cls.env['stock.quant']._update_available_quantity(cls.tinte, cls.stock, 1)

        cls.horario = cls.env.ref('studio_bella.horario_studio_bella').copy({'company_id': cls.company.id})
        cls.estilista = cls.env['hr.employee'].create({
            'name': 'Estilista de prueba',
            'bella_estilista': True,
            'resource_calendar_id': cls.horario.id,
            'tz': 'America/Asuncion',
            'bella_servicio_ids': [Command.set((cls.corte | cls.color).ids)],
        })
        cls.cliente = cls.env['res.partner'].create({'name': 'Cliente de prueba', 'email': 'cliente@example.com'})
        # Lunes 2 de noviembre de 2026 a las 10:00 de Asunción (UTC-3).
        cls.lunes_10 = datetime(2026, 11, 2, 13, 0)

    def _cita(self, inicio=None, servicios=None, **valores):
        servicios = self.corte if servicios is None else servicios
        return self.env['bella.cita'].create({
            'cliente_id': self.cliente.id,
            'estilista_id': self.estilista.id,
            'fecha_inicio': inicio or self.lunes_10,
            'servicio_ids': [Command.create({'servicio_id': servicio.id}) for servicio in servicios],
            **valores,
        })

    def _cobrar(self, documento, metodo='efectivo', monto_recibido=0):
        campo = 'cita_id' if documento._name == 'bella.cita' else 'venta_id'
        wizard = Form(self.env['bella.cobro.wizard'].with_context(**{f'default_{campo}': documento.id}))
        wizard.metodo_pago = metodo
        if monto_recibido:
            wizard.monto_recibido = monto_recibido
        wizard = wizard.save()
        vuelto = wizard.vuelto
        wizard.action_cobrar()
        return vuelto

    def _stock(self, producto):
        return producto.with_context(location=self.stock.id).qty_available
