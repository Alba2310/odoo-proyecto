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

from .atencion import AREAS_AGENDA, LIBERAN, MINUTOS_MINIMOS
from .utiles import EMOJIS, numero_whatsapp, primer_nombre

# Página de turnos para los dueños (/reservar)
DIAS_A_LA_VISTA = 14  # Hasta cuántos días adelante se puede reservar.
ANTICIPACION_MINUTOS = 60  # No se reserva un turno que empieza dentro de menos de una hora.
PASO_MINUTOS = 30  # Los turnos empiezan en punto o y media.
MAXIMO_PENDIENTES = 3  # Turnos por venir que un mismo dueño puede tener pedidos por internet.


class VetReserva(models.AbstractModel):
    """Turnos por internet: lo que muestra y guarda la página pública /reservar.

    El controlador lo usa con sudo(), porque el dueño no tiene usuario en Odoo. Los horarios libres salen del
    horario de cada profesional (con feriados y ausencias) menos los turnos que ya tiene.
    """
    _name = 'vet.reserva'
    _description = 'Turnos por internet'

    @api.model
    def _idioma(self):
        idioma = self.env.company.partner_id.lang
        return idioma if idioma and idioma.startswith('es') else self.env.lang

    @api.model
    def _servicios(self, especie=None):
        """Lo que los dueños pueden pedir solos: consultas, vacunas, baños... Con especie, solo lo que es para ella."""
        servicios = self.env['product.product'].search([
            ('vet_reserva_online', '=', True),
            ('vet_area', 'in', [clave for clave, _nombre in AREAS_AGENDA]),
            ('sale_ok', '=', True),
            ('company_id', 'in', (False, self.env.company.id)),
        ], order='vet_area, list_price, name')
        if especie:
            servicios = servicios.filtered(lambda s: not s.vet_especie_ids or especie in s.vet_especie_ids)
        return servicios

    @api.model
    def _profesionales(self, area, servicios=None):
        """Quienes atienden en el área, tienen horario y hacen todo lo pedido."""
        profesionales = self.env['hr.employee'].search([
            ('vet_atiende', 'in', (area, 'ambas')),
            ('resource_calendar_id', '!=', False),
            ('company_id', '=', self.env.company.id),
        ], order='name')
        pedidos = (servicios or self.env['product.product']).filtered(lambda producto: producto.type == 'service')
        return profesionales.filtered(lambda p: not p.vet_servicio_ids or pedidos <= p.vet_servicio_ids)

    @api.model
    def _area(self, servicios):
        areas = set(servicios.mapped('vet_area'))
        if len(areas) != 1:
            raise UserError('Elegí servicios de una sola área: consultorio o baño y peluquería.')
        return areas.pop()

    @api.model
    def _duracion(self, servicios):
        return timedelta(minutes=sum(servicios.mapped('vet_duracion')) or MINUTOS_MINIMOS)

    @api.model
    def _zona_horaria(self, profesionales=None):
        profesional = profesionales[:1] if profesionales else self.env['hr.employee']
        return pytz.timezone(profesional.tz or self.env.company.resource_calendar_id.tz or 'America/Asuncion')

    # Horarios libres

    @api.model
    def _libres(self, servicios, profesional=None, ahora=None):
        """``{inicio (UTC, sin zona): profesionales libres}`` para hacer los servicios."""
        ahora = ahora or fields.Datetime.now()
        if not servicios:
            return {}
        candidatos = self._profesionales(self._area(servicios), servicios)
        if profesional:
            candidatos &= profesional
        if not candidatos:
            return {}
        duracion = self._duracion(servicios)
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
    def _inicios_libres(self, profesional, duracion, desde, hasta):
        """Horas (UTC, sin zona) en las que el profesional puede empezar un turno de esa duración."""
        horario = profesional.resource_calendar_id
        recurso = profesional.resource_id
        tz = pytz.timezone(profesional.tz or horario.tz or 'UTC')
        intervalos = horario._work_intervals_batch(
            pytz.utc.localize(desde), pytz.utc.localize(hasta), resources=recurso)[recurso.id]
        # Se juntan la mañana y la tarde cuando son seguidas, para que un turno pueda pasar del mediodía.
        tramos = []
        for inicio, fin, _registros in intervalos:
            if tramos and inicio <= tramos[-1][1]:
                tramos[-1][1] = max(tramos[-1][1], fin)
            else:
                tramos.append([inicio, fin])
        ocupados = [(atencion.fecha_inicio, atencion.fecha_fin) for atencion in self.env['vet.atencion'].search([
            ('profesional_id', '=', profesional.id),
            ('estado', 'not in', LIBERAN),
            ('fecha_inicio', '<', hasta),
            ('fecha_fin', '>', desde),
        ])]
        paso = timedelta(minutes=PASO_MINUTOS)
        inicios = []
        for inicio_tramo, fin_tramo in tramos:
            local = inicio_tramo.astimezone(tz)
            redondo = local.replace(minute=0, second=0, microsecond=0)
            while redondo < local:
                redondo += paso
            momento = redondo.astimezone(pytz.utc).replace(tzinfo=None)
            fin = fin_tramo.astimezone(pytz.utc).replace(tzinfo=None)
            while momento + duracion <= fin:
                termina = momento + duracion
                if momento >= desde and not any(ini < termina and hasta_ocupado > momento
                                                for ini, hasta_ocupado in ocupados):
                    inicios.append(momento)
                momento += paso
        return inicios

    @api.model
    def _dias(self, servicios, profesional=None, ahora=None):
        """Los próximos días con sus horarios libres, para la página."""
        ahora = ahora or fields.Datetime.now()
        libres = self._libres(servicios, profesional, ahora)
        tz = self._zona_horaria(profesional or (self._profesionales(self._area(servicios), servicios)
                                                if servicios else None))
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
                'semana': 'Hoy' if not numero else 'Mañana' if numero == 1 else
                          format_date(self.env, dia, date_format='EEEE').capitalize(),
                'dia': dia.day,
                'mes': format_date(self.env, dia, date_format='MMMM'),
                'horarios': por_dia.get(dia, []),
            })
        return dias

    # Reserva

    @api.model
    def _reservar(self, servicios, inicio, datos, profesional=None, ahora=None):
        """Da el turno que pidió el dueño. ``datos``: mascota, especie_id, nombre, telefono, email y nota."""
        ahora = ahora or fields.Datetime.now()
        nombre = (datos.get('nombre') or '').strip()
        nombre_mascota = (datos.get('mascota') or '').strip()
        email = (datos.get('email') or '').strip()
        especie = self.env['vet.especie'].browse(int(datos.get('especie_id') or 0)).exists()
        if not nombre_mascota:
            raise UserError('Escribí el nombre de tu mascota.')
        if not especie:
            raise UserError('Contanos qué animal es tu mascota.')
        if not servicios:
            raise UserError('Elegí qué necesita tu mascota.')
        if servicios - self._servicios(especie):
            raise UserError('Alguno de los servicios ya no se puede pedir por internet. Elegilos de nuevo, por favor.')
        area = self._area(servicios)
        if not nombre:
            raise UserError('Escribí tu nombre.')
        codigo_pais = str(self.env.company.country_id.phone_code or 595)
        numero = numero_whatsapp(datos.get('telefono'), codigo_pais)
        if len(numero) < 10:
            raise UserError('Revisá el número de celular: escribilo con la característica, por ejemplo 0981 123 456.')
        if email and not single_email_re.match(email):
            raise UserError('Revisá el correo: parece que le falta algo.')

        libres = self._libres(servicios, profesional, ahora).get(inicio)
        if not libres:
            raise UserError('Ese horario ya no está libre. Elegí otro, por favor.')
        dueno = self._dueno(nombre, datos.get('telefono'), numero, email, codigo_pais)
        pendientes = self.env['vet.atencion'].search_count([
            ('dueno_id', '=', dueno.id),
            ('origen', '=', 'internet'),
            ('estado', '=', 'reservada'),
            ('fecha_inicio', '>', ahora),
        ])
        if pendientes >= MAXIMO_PENDIENTES:
            raise UserError(f'Ya tenés {pendientes} turnos pedidos. Para sacar otro, escribinos o llamanos.')
        mascota = self._mascota(dueno, nombre_mascota, especie)
        elegido = self._elegir_profesional(libres, inicio)
        # Si dos dueños eligen el mismo horario a la vez, el segundo choca acá: Odoo repite su pedido y la
        # validación del turno ve el del primero.
        self.env.cr.execute('UPDATE hr_employee SET write_date = write_date WHERE id = %s', [elegido.id])
        atencion = self.env['vet.atencion'].create({
            'area': area,
            'mascota_id': mascota.id,
            'profesional_id': elegido.id,
            'fecha_inicio': inicio,
            'linea_ids': [Command.create({'producto_id': servicio.id}) for servicio in servicios],
            'motivo': (datos.get('nota') or '').strip()[:300] or False,
            'origen': 'internet',
        })
        mensaje = Markup('Turno pedido por internet.')
        if dueno.name.casefold() != nombre.casefold():
            mensaje += Markup('<br/>Nombre que escribió: %s.') % nombre
        atencion.message_post(body=mensaje)
        return atencion

    @api.model
    def _elegir_profesional(self, profesionales, inicio):
        """Entre los libres, quien tiene menos turnos ese día."""
        if len(profesionales) == 1:
            return profesionales
        tz = self._zona_horaria(profesionales)
        dia = pytz.utc.localize(inicio).astimezone(tz).date()
        desde = tz.localize(datetime.combine(dia, time.min)).astimezone(pytz.utc).replace(tzinfo=None)
        cantidades = dict(self.env['vet.atencion']._read_group([
            ('profesional_id', 'in', profesionales.ids),
            ('estado', 'not in', LIBERAN),
            ('fecha_inicio', '>=', desde),
            ('fecha_inicio', '<', desde + timedelta(days=1)),
        ], ['profesional_id'], ['__count']))
        return min(profesionales, key=lambda profesional: (cantidades.get(profesional, 0), profesional.name))

    @api.model
    def _dueno(self, nombre, telefono, numero, email, codigo_pais):
        """El dueño se reconoce por el celular; si es la primera vez, se lo agrega a los contactos."""
        parecidos = self.env['res.partner'].search([
            '|', ('mobile', 'ilike', numero[-3:]), ('phone', 'ilike', numero[-3:]),
        ])
        dueno = parecidos.filtered(lambda partner: numero in (
            numero_whatsapp(partner.mobile, codigo_pais), numero_whatsapp(partner.phone, codigo_pais)))[:1]
        if dueno:
            if email and not dueno.email:
                dueno.email = email
            return dueno
        return self.env['res.partner'].create({
            'name': nombre[:80],
            'mobile': (telefono or '').strip(),
            'email': email or False,
            'customer_rank': 1,
        })

    @api.model
    def _mascota(self, dueno, nombre, especie):
        """La mascota del dueño con ese nombre (sin importar mayúsculas); si no está, se la agrega."""
        mascota = self.env['vet.mascota'].search([
            ('dueno_id', '=', dueno.id), ('company_id', '=', self.env.company.id), ('fallecida', '=', False),
        ]).filtered(lambda m: m.name.casefold() == nombre.casefold() and m.especie_id == especie)[:1]
        if mascota:
            return mascota
        return self.env['vet.mascota'].create({
            'name': nombre[:60],
            'dueno_id': dueno.id,
            'especie_id': especie.id,
            'company_id': self.env.company.id,
        })

    # Datos para la página

    @api.model
    def _datos_pagina(self):
        company = self.env.company
        moneda = company.currency_id
        codigo_pais = str(company.country_id.phone_code or 595)
        servicios = self._servicios()
        especies = self.env['vet.especie'].search([])
        return {
            'clinica': company.name,
            'telefono': company.phone or '',
            'whatsapp': numero_whatsapp(company.mobile, codigo_pais),
            'moneda': {'simbolo': moneda.symbol, 'antes': moneda.position == 'before',
                       'decimales': moneda.decimal_places},
            'especies': [{'id': especie.id, 'nombre': especie.name,
                          'emoji': EMOJIS.get(especie.icono, EMOJIS['otro'])} for especie in especies],
            'areas': [{'clave': clave, 'nombre': nombre} for clave, nombre in AREAS_AGENDA],
            'servicios': [{
                'id': servicio.id,
                'nombre': servicio.name,
                'area': servicio.vet_area,
                'duracion': servicio.vet_duracion or MINUTOS_MINIMOS,
                'precio': servicio.lst_price,
                'especies': servicio.vet_especie_ids.ids,
                # Solo los servicios cuentan para "qué hace cada profesional" (una vacuna la aplica cualquiera).
                'es_servicio': servicio.type == 'service',
            } for servicio in servicios],
            'profesionales': [{
                'id': profesional.id,
                'nombre': profesional.name,
                'areas': ['consultorio', 'estetica'] if profesional.vet_atiende == 'ambas' else [profesional.vet_atiende],
                'servicios': profesional.vet_servicio_ids.ids,
            } for profesional in self._profesionales('consultorio') | self._profesionales('estetica')],
        }

    @api.model
    def _confirmacion(self, atencion, nombre):
        """Lo que ve el dueño después de reservar."""
        atencion = atencion.with_context(lang=self._idioma())
        clinica = atencion.company_id
        numero = numero_whatsapp(clinica.mobile, str(clinica.country_id.phone_code or 595))
        texto = (f'¡Hola! Soy {nombre.strip()}. Pedí un turno por internet para {atencion.mascota_id.name} el '
                 f'{atencion.turno_texto} ({atencion.servicios_texto}).')
        return {
            'nombre': primer_nombre(nombre.strip()),
            'mascota': atencion.mascota_id.name,
            'turno': atencion.turno_texto,
            'profesional': atencion.profesional_id.name,
            'servicios': atencion.servicios_texto,
            'whatsapp': f'https://wa.me/{numero}?text={quote(texto)}' if numero else False,
        }
