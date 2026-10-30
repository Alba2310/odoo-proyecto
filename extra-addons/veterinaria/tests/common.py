# -*- coding: utf-8 -*-
from datetime import date, datetime

from odoo import Command
from odoo.tests import Form

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


class PatitasCommon(AccountTestInvoicingCommon):
    """Servicios, una vacuna y un alimento con stock, una veterinaria y una peluquera con el horario de Patitas, una
    dueña con su perro, y una jaula y un canil."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.groups_id += cls.env.ref('veterinaria.group_vet_admin')
        cls.company = cls.env.company
        # En Paraguay: los números de WhatsApp llevan el 595.
        cls.company.country_id = cls.env.ref('base.py')
        cls.warehouse = cls.env['stock.warehouse'].search([('company_id', '=', cls.company.id)], limit=1)
        cls.stock = cls.warehouse.lot_stock_id
        cls.perro = cls.env.ref('veterinaria.especie_perro')
        cls.gato = cls.env.ref('veterinaria.especie_gato')

        # IVA 10 % incluido en el precio, como en Paraguay.
        cls.iva_10 = cls.env['account.tax'].create({
            'name': 'IVA 10 % de prueba',
            'amount': 10,
            'type_tax_use': 'sale',
            'price_include_override': 'tax_included',
        })
        iva = [Command.set(cls.iva_10.ids)]
        Producto = cls.env['product.product']
        cls.consulta = Producto.create({
            'name': 'Consulta de prueba', 'type': 'service', 'list_price': 100, 'taxes_id': iva,
            'vet_area': 'consultorio', 'vet_duracion': 30, 'vet_reserva_online': True,
        })
        cls.antirrabica = Producto.create({
            'name': 'Antirrábica de prueba', 'type': 'consu', 'is_storable': True, 'list_price': 60, 'taxes_id': iva,
            'vet_area': 'consultorio', 'vet_duracion': 15, 'vet_reserva_online': True,
            'vet_aplicacion': 'vacuna', 'vet_dias_refuerzo': 365,
            'vet_especie_ids': [Command.set((cls.perro | cls.gato).ids)],
        })
        cls.bano = Producto.create({
            'name': 'Baño de prueba', 'type': 'service', 'list_price': 80, 'taxes_id': iva,
            'vet_area': 'estetica', 'vet_duracion': 60, 'vet_reserva_online': True,
            'vet_especie_ids': [Command.set(cls.perro.ids)],
        })
        cls.alimento = Producto.create({
            'name': 'Alimento de prueba', 'type': 'consu', 'is_storable': True, 'list_price': 200, 'taxes_id': iva,
        })
        cls.dia_internacion = Producto.create({
            'name': 'Día de internación de prueba', 'type': 'service', 'list_price': 150, 'taxes_id': iva,
            'vet_area': 'internacion',
        })
        cls.dia_hotel = Producto.create({
            'name': 'Día de hotel de prueba', 'type': 'service', 'list_price': 50, 'taxes_id': iva,
            'vet_area': 'internacion',
        })
        cls.company.write({
            'vet_producto_internacion_id': cls.dia_internacion.id,
            'vet_producto_hotel_id': cls.dia_hotel.id,
        })
        cls.env['stock.quant']._update_available_quantity(cls.alimento, cls.stock, 5)
        cls.env['stock.quant']._update_available_quantity(cls.antirrabica, cls.stock, 3)

        cls.horario = cls.env.ref('veterinaria.horario_patitas').copy({'company_id': cls.company.id})
        cls.veterinaria = cls.env['hr.employee'].create({
            'name': 'Veterinaria de prueba', 'vet_atiende': 'consultorio', 'vet_matricula': 'MP 123',
            'resource_calendar_id': cls.horario.id, 'tz': 'America/Asuncion',
        })
        cls.peluquera = cls.env['hr.employee'].create({
            'name': 'Peluquera de prueba', 'vet_atiende': 'estetica',
            'resource_calendar_id': cls.horario.id, 'tz': 'America/Asuncion',
        })
        cls.duena = cls.env['res.partner'].create({
            'name': 'Ana Dueña', 'mobile': '0981 000 900', 'email': 'ana@example.com',
        })
        cls.toby = cls.env['vet.mascota'].create({
            'name': 'Toby', 'dueno_id': cls.duena.id, 'especie_id': cls.perro.id, 'sexo': 'macho',
            'fecha_nacimiento': date(2022, 3, 10),
        })
        cls.jaula = cls.env['vet.lugar'].create({'name': 'Jaula de prueba', 'tipo': 'internacion'})
        cls.canil = cls.env['vet.lugar'].create({'name': 'Canil de prueba', 'tipo': 'hotel'})
        # Lunes 2 de noviembre de 2026 a las 10:00 de Asunción (UTC-3).
        cls.lunes_10 = datetime(2026, 11, 2, 13, 0)

    def _atencion(self, inicio=None, productos=None, sin_horario=False, **valores):
        """Un turno de Toby con la veterinaria. ``sin_horario``: para turnos relativos a hoy, que pueden caer fuera
        del horario según la hora a la que corren los tests."""
        productos = self.consulta if productos is None else productos
        return self.env['vet.atencion'].with_context(vet_sin_horario=sin_horario).create({
            'mascota_id': self.toby.id,
            'profesional_id': self.veterinaria.id,
            'fecha_inicio': inicio or self.lunes_10,
            'linea_ids': [Command.create({'producto_id': producto.id}) for producto in productos],
            **valores,
        })

    def _cobrar(self, documento, tarjeta=0, transferencia=0, entrega=0):
        """Cobra con el asistente de la caja; lo que no va con tarjeta ni transferencia queda en efectivo."""
        campo = {'vet.atencion': 'atencion_id', 'vet.internacion': 'internacion_id', 'vet.venta': 'venta_id'}
        wizard = Form(self.env['vet.cobro.wizard'].with_context(**{f'default_{campo[documento._name]}': documento.id}))
        wizard.tarjeta = tarjeta
        wizard.transferencia = transferencia
        if entrega:
            wizard.entrega = entrega
        wizard = wizard.save()
        vuelto = wizard.vuelto
        wizard.action_cobrar()
        return vuelto

    def _stock(self, producto):
        return producto.with_context(location=self.stock.id).qty_available
