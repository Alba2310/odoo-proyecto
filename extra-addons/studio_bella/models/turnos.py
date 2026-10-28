# -*- coding: utf-8 -*-
from collections import defaultdict
from datetime import datetime, time, timedelta
from urllib.parse import quote

import pytz
from markupsafe import Markup

from odoo import Command, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_date
from odoo.tools.mail import single_email_re

from .cita import ESTADOS_LIBRES, MINUTOS_SIN_SERVICIOS, numero_whatsapp

# Página de turnos para las clientas (/turnos)
DIAS_A_LA_VISTA = 14  # Hasta cuántos días adelante se puede reservar.
ANTICIPACION_MINUTOS = 60  # No se reserva un turno que empieza dentro de menos de una hora.
PASO_MINUTOS = 30  # Los turnos empiezan en punto o y media.
MAXIMO_TURNOS_PENDIENTES = 3  # Turnos por venir que una misma clienta puede tener reservados por internet.


class BellaTurnos(models.AbstractModel):
    """Reserva de turnos por internet: lo que muestra y guarda la página pública /turnos.

    El controlador lo usa con sudo(), porque la clienta no tiene usuario en Odoo. Los horarios libres salen del
    horario de cada estilista (con sus feriados y ausencias) y de las citas que ya tiene, igual que en la agenda.
    """
    _name = 'bella.turnos'
    _description = 'Turnos por internet'

    @api.model
    def _idioma(self):
        """La página está en español: fechas y precios con el idioma de la peluquería."""
        idioma = self.env.company.partner_id.lang
        return idioma if idioma and idioma.startswith('es') else self.env.lang

    @api.model
    def _servicios(self):
        """Servicios que las clientas pueden reservar solas."""
        categoria = self.env.ref('studio_bella.categoria_servicios')
        return self.env['product.product'].search([
            ('type', '=', 'service'),
            ('categ_id', 'child_of', categoria.id),
            ('bella_reserva_online', '=', True),
            ('company_id', 'in', (False, self.env.company.id)),
        ], order='categ_id, list_price, name')

    @api.model
    def _estilistas(self, servicios):
        """Estilistas con horario de trabajo que hacen todos los servicios elegidos."""
        estilistas = self.env['hr.employee'].search([
            ('bella_estilista', '=', True),
            ('resource_calendar_id', '!=', False),
            ('company_id', '=', self.env.company.id),
        ], order='name')
        return estilistas.filtered(
            lambda estilista: not estilista.bella_servicio_ids or servicios <= estilista.bella_servicio_ids)

    @api.model
    def _zona_horaria(self, estilistas):
        return pytz.timezone(estilistas[:1].tz or self.env.company.resource_calendar_id.tz or 'UTC')

    # Horarios libres

    @api.model
    def _disponibilidad(self, servicios, estilista=None, ahora=None):
        """Horarios en los que se pueden hacer los servicios: ``{inicio (UTC): estilistas libres}``.

        Sin estilista, junta los horarios de todos los que hacen esos servicios.
        """
        ahora = ahora or fields.Datetime.now()
        candidatos = self._estilistas(servicios)
        if estilista:
            candidatos &= estilista
        if not servicios or not candidatos:
            return {}
        duracion = timedelta(minutes=sum(servicios.mapped('bella_duracion')) or MINUTOS_SIN_SERVICIOS)
        desde = ahora + timedelta(minutes=ANTICIPACION_MINUTOS)
        tz = self._zona_horaria(candidatos)
        hoy = pytz.utc.localize(ahora).astimezone(tz).date()
        hasta = tz.localize(datetime.combine(hoy + timedelta(days=DIAS_A_LA_VISTA), time.min))
        hasta = hasta.astimezone(pytz.utc).replace(tzinfo=None)

        libres = defaultdict(lambda: self.env['hr.employee'])
        for candidato in candidatos:
            for inicio in self._inicios_libres(candidato, duracion, desde, hasta):
                libres[inicio] |= candidato
        return dict(sorted(libres.items()))

    @api.model
    def _inicios_libres(self, estilista, duracion, desde, hasta):
        """Horas (UTC, sin zona) en las que el estilista puede empezar un turno de esa duración."""
        horario = estilista.resource_calendar_id
        recurso = estilista.resource_id
        tz = pytz.timezone(estilista.tz or horario.tz or 'UTC')
        # Ya descuenta los feriados, los cierres y las ausencias del estilista.
        intervalos = horario._work_intervals_batch(
            pytz.utc.localize(desde), pytz.utc.localize(hasta), resources=recurso)[recurso.id]
        # Se juntan los tramos seguidos (mañana y tarde) para que un turno pueda pasar del mediodía.
        tramos = []
        for inicio, fin, _registros in intervalos:
            if tramos and inicio <= tramos[-1][1]:
                tramos[-1][1] = max(tramos[-1][1], fin)
            else:
                tramos.append([inicio, fin])

        ocupados = [(cita.fecha_inicio, cita.fecha_fin) for cita in self.env['bella.cita'].search([
            ('estilista_id', '=', estilista.id),
            ('estado', 'not in', ESTADOS_LIBRES),
            ('fecha_inicio', '<', hasta),
            ('fecha_fin', '>', desde),
        ])]
        paso = timedelta(minutes=PASO_MINUTOS)
        inicios = []
        for inicio_tramo, fin_tramo in tramos:
            # Primer horario redondo del tramo, en la hora de la peluquería.
            local = inicio_tramo.astimezone(tz)
            redondo = local.replace(minute=0, second=0, microsecond=0)
            while redondo < local:
                redondo += paso
            momento = redondo.astimezone(pytz.utc).replace(tzinfo=None)
            fin = fin_tramo.astimezone(pytz.utc).replace(tzinfo=None)
            while momento + duracion <= fin:
                termina = momento + duracion
                if momento >= desde and not any(ini < termina and fin_ocupado > momento for ini, fin_ocupado in ocupados):
                    inicios.append(momento)
                momento += paso
        return inicios

    @api.model
    def _dias(self, servicios, estilista=None, ahora=None):
        """Los próximos días con sus horarios libres, para la página."""
        ahora = ahora or fields.Datetime.now()
        libres = self._disponibilidad(servicios, estilista, ahora)
        tz = self._zona_horaria(estilista or self._estilistas(servicios))
        por_dia = defaultdict(list)
        for inicio in libres:
            local = pytz.utc.localize(inicio).astimezone(tz)
            por_dia[local.date()].append({'hora': local.strftime('%H:%M'), 'inicio': fields.Datetime.to_string(inicio)})
        hoy = pytz.utc.localize(ahora).astimezone(tz).date()
        dias = []
        for numero in range(DIAS_A_LA_VISTA):
            dia = hoy + timedelta(days=numero)
            dias.append({
                'fecha': dia.isoformat(),
                'semana': format_date(self.env, dia, date_format='EEE').rstrip('.'),
                'dia': dia.day,
                'mes': format_date(self.env, dia, date_format='MMM').rstrip('.'),
                'horarios': por_dia.get(dia, []),
            })
        return dias

    # Reserva

    @api.model
    def _reservar(self, servicios, inicio, nombre, telefono, estilista=None, email=None, nota=None, ahora=None):
        """Agenda el turno que pidió la clienta. Devuelve la cita."""
        ahora = ahora or fields.Datetime.now()
        nombre = (nombre or '').strip()
        email = (email or '').strip()
        if not servicios:
            raise UserError('Elegí al menos un servicio.')
        if servicios - self._servicios():
            raise UserError('Alguno de los servicios ya no se puede reservar por internet. Elegilos de nuevo, por favor.')
        if not nombre:
            raise UserError('Escribí tu nombre.')
        codigo_pais = str(self.env.company.country_id.phone_code or 595)
        numero = numero_whatsapp(telefono, codigo_pais)
        if len(numero) < 10:
            raise UserError('Revisá el número de celular: escribilo con la característica, por ejemplo 0981 123 456.')
        if email and not single_email_re.match(email):
            raise UserError('Revisá el correo: parece que le falta algo.')

        libres = self._disponibilidad(servicios, estilista, ahora).get(inicio)
        if not libres:
            raise UserError('Ese horario ya no está libre. Elegí otro, por favor.')
        estilista = self._elegir_estilista(libres, inicio)
        cliente = self._cliente(nombre, telefono, numero, email, codigo_pais)
        pendientes = self.env['bella.cita'].search_count([
            ('cliente_id', '=', cliente.id),
            ('origen', '=', 'internet'),
            ('estado', 'in', ('agendada', 'confirmada')),
            ('fecha_inicio', '>', ahora),
        ])
        if pendientes >= MAXIMO_TURNOS_PENDIENTES:
            raise UserError(f'Ya tenés {pendientes} turnos reservados. Para sacar otro, escribinos o llamanos.')

        # Si dos clientas eligen el mismo horario a la vez, la segunda choca acá: Odoo repite su pedido y la
        # validación de la cita ve el turno de la primera.
        self.env.cr.execute('UPDATE hr_employee SET write_date = write_date WHERE id = %s', [estilista.id])
        cita = self.env['bella.cita'].create({
            'cliente_id': cliente.id,
            'estilista_id': estilista.id,
            'fecha_inicio': inicio,
            'servicio_ids': [Command.create({'servicio_id': servicio.id}) for servicio in servicios],
            'nota': (nota or '').strip()[:500] or False,
            'origen': 'internet',
        })
        mensaje = 'Turno pedido por internet desde la página de turnos.'
        if cliente.name.casefold() != nombre.casefold():
            mensaje += Markup('<br/>Nombre que escribió: %s.') % nombre
        cita.message_post(body=mensaje)
        return cita

    @api.model
    def _elegir_estilista(self, estilistas, inicio):
        """Entre los estilistas libres, el que tiene menos turnos ese día."""
        if len(estilistas) == 1:
            return estilistas
        tz = self._zona_horaria(estilistas)
        dia = pytz.utc.localize(inicio).astimezone(tz).date()
        desde = tz.localize(datetime.combine(dia, time.min)).astimezone(pytz.utc).replace(tzinfo=None)
        cantidades = dict(self.env['bella.cita']._read_group([
            ('estilista_id', 'in', estilistas.ids),
            ('estado', 'not in', ESTADOS_LIBRES),
            ('fecha_inicio', '>=', desde),
            ('fecha_inicio', '<', desde + timedelta(days=1)),
        ], ['estilista_id'], ['__count']))
        return min(estilistas, key=lambda estilista: (cantidades.get(estilista, 0), estilista.name))

    @api.model
    def _cliente(self, nombre, telefono, numero, email, codigo_pais):
        """La clienta se reconoce por el celular; si es la primera vez, se la agrega a los clientes."""
        parecidos = self.env['res.partner'].search([
            '|', ('mobile', 'ilike', numero[-3:]), ('phone', 'ilike', numero[-3:]),
        ])
        cliente = parecidos.filtered(lambda partner: numero in (
            numero_whatsapp(partner.mobile, codigo_pais), numero_whatsapp(partner.phone, codigo_pais)))[:1]
        if cliente:
            if email and not cliente.email:
                cliente.email = email
            return cliente
        return self.env['res.partner'].create({
            'name': nombre[:80],
            'phone': telefono.strip(),
            'email': email or False,
            'customer_rank': 1,
        })

    # Datos para la página

    @api.model
    def _datos_pagina(self):
        company = self.env.company
        moneda = company.currency_id
        categorias = []
        for servicio in self._servicios():
            if not categorias or categorias[-1]['id'] != servicio.categ_id.id:
                categorias.append({'id': servicio.categ_id.id, 'nombre': servicio.categ_id.name, 'servicios': []})
            categorias[-1]['servicios'].append({
                'id': servicio.id,
                'nombre': servicio.name,
                'duracion': servicio.bella_duracion,
                'precio': servicio.lst_price,
            })
        codigo_pais = str(company.country_id.phone_code or 595)
        return {
            'salon': company.name,
            'telefono': company.phone or '',
            'whatsapp': numero_whatsapp(company.mobile, codigo_pais),
            'moneda': {
                'simbolo': moneda.symbol,
                'antes': moneda.position == 'before',
                'decimales': moneda.decimal_places,
            },
            'categorias': categorias,
            'estilistas': [{
                'id': estilista.id,
                'nombre': estilista.name,
                'servicios': estilista.bella_servicio_ids.ids,
            } for estilista in self._estilistas(self.env['product.product'])],
        }

    @api.model
    def _confirmacion(self, cita, nombre):
        """Lo que ve la clienta después de reservar."""
        cita = cita.with_context(lang=self._idioma())
        salon = cita.company_id
        numero = numero_whatsapp(salon.mobile, str(salon.country_id.phone_code or 595))
        texto = (f'¡Hola! Soy {nombre.strip()}. Reservé un turno por internet para el {cita.turno_texto} '
                 f'({cita.servicios_texto}) con {cita.estilista_id.name}.')
        return {
            'nombre': nombre.strip().split()[0],
            'turno': cita.turno_texto,
            'estilista': cita.estilista_id.name,
            'servicios': cita.servicios_texto,
            'whatsapp': f'https://wa.me/{numero}?text={quote(texto)}' if numero else False,
        }
