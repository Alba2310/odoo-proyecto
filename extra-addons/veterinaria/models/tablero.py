# -*- coding: utf-8 -*-
from datetime import datetime, time, timedelta

import pytz

from odoo import api, fields, models
from odoo.tools import format_amount

from .atencion import AREAS_AGENDA
from .utiles import fecha_con_dia, fecha_corta

# Un turno reservado se marca como atrasado si pasaron estos minutos de la hora y no llegó.
MINUTOS_ATRASO = 15

COLUMNAS = [
    ('reservada', 'Turnos de hoy', 'Todavía no llegaron'),
    ('en_espera', 'Sala de espera', 'Llegaron y esperan'),
    ('en_curso', 'En atención', 'En el consultorio o en la bañera'),
    ('lista', 'Para retirar y cobrar', 'Terminadas'),
]


class VetTablero(models.AbstractModel):
    """Los datos de "Hoy en Patitas" (static/src/tablero): la sala de espera, los internados y hospedados, y lo
    que hay que avisar o reponer. Son los de la compañía activa."""
    _name = 'vet.tablero'
    _description = 'Hoy en Patitas'

    def _tz(self):
        return pytz.timezone(self.env.user.tz or self.env.company.resource_calendar_id.tz or 'America/Asuncion')

    def _hace(self, desde, ahora):
        """'recién', 'hace 12 min', 'hace 1 h 20 min', 'hace 2 días'."""
        if not desde:
            return ''
        minutos = int((ahora - desde).total_seconds() // 60)
        if minutos < 2:
            return 'recién'
        if minutos < 60:
            return f'hace {minutos} min'
        horas, minutos = divmod(minutos, 60)
        if horas >= 48:
            return f'hace {horas // 24} días'
        return f'hace {horas} h' + (f' {minutos} min' if minutos else '')

    def _foto(self, mascota):
        return f'/web/image/vet.mascota/{mascota.id}/foto/128x128' if mascota.foto else False

    @api.model
    def datos(self, area=None):
        ahora = fields.Datetime.now()
        tz = self._tz()
        hoy = pytz.utc.localize(ahora).astimezone(tz).date()
        inicio_dia = tz.localize(datetime.combine(hoy, time.min)).astimezone(pytz.utc).replace(tzinfo=None)
        fin_dia = inicio_dia + timedelta(days=1)
        company = self.env.company
        dominio_area = [('area', '=', area)] if area in dict(AREAS_AGENDA) else []

        Atencion = self.env['vet.atencion']
        # Los turnos de hoy y lo que quedó adentro (una mascota que llegó ayer y sigue esperando que la retiren).
        atenciones = Atencion.search([('company_id', '=', company.id)] + dominio_area + [
            '|', '&', ('estado', '=', 'reservada'), '&', ('fecha_inicio', '>=', inicio_dia), ('fecha_inicio', '<', fin_dia),
            ('estado', 'in', ('en_espera', 'en_curso', 'lista')),
        ], order='fecha_inicio, id')
        columnas = []
        for clave, titulo, ayuda in COLUMNAS:
            propias = atenciones.filtered(lambda atencion: atencion.estado == clave)
            columnas.append({
                'clave': clave, 'titulo': titulo, 'ayuda': ayuda,
                'tarjetas': [self._tarjeta(atencion, ahora) for atencion in propias],
            })

        return {
            'hoy': fecha_con_dia(hoy).capitalize(),
            'area': area or False,
            'areas': [{'clave': clave, 'nombre': nombre} for clave, nombre in AREAS_AGENDA],
            'columnas': columnas,
            'estadias': self._estadias(ahora, hoy, tz),
            'avisos': self._avisos(hoy, inicio_dia, fin_dia),
        }

    def _tarjeta(self, atencion, ahora):
        mascota = atencion.mascota_id
        desde = {'en_espera': atencion.llegada, 'en_curso': atencion.inicio_atencion,
                 'lista': atencion.fin_atencion}.get(atencion.estado)
        return {
            'id': atencion.id,
            'mascota': mascota.name,
            'mascota_id': mascota.id,
            'emoji': mascota.emoji,
            'foto': self._foto(mascota),
            'detalle': ' · '.join(parte for parte in (mascota.raza_id.name or mascota.especie_id.name, mascota.edad)
                                  if parte),
            'dueno': atencion.dueno_id.name,
            'area': atencion.area,
            'servicios': atencion.servicios_texto or atencion.motivo or '',
            'profesional': atencion.profesional_id.name or 'Sin asignar',
            'hora': atencion.hora_texto,
            'desde': self._hace(desde, ahora),
            'alertas': mascota.alertas or '',
            'internet': atencion.origen == 'internet',
            'sin_turno': atencion.origen == 'sin_turno',
            'atrasado': atencion.estado == 'reservada'
                        and atencion.fecha_inicio + timedelta(minutes=MINUTOS_ATRASO) < ahora,
            'avisada': bool(atencion.aviso_lista_el),
            'total': format_amount(self.env, atencion.total, atencion.currency_id) if atencion.total else '',
        }

    def _estadias(self, ahora, hoy, tz):
        horas_control = self.env.company.vet_horas_control
        estadias = self.env['vet.internacion'].search([
            ('company_id', '=', self.env.company.id),
            '|', ('estado', 'in', ('activa', 'alta')),
            '&', ('estado', '=', 'reservada'), ('ingreso', '<', ahora + timedelta(days=1)),
        ], order='estado, ingreso')
        resultado = []
        for estadia in estadias:
            mascota = estadia.mascota_id
            ultimo = estadia.ultimo_control or (estadia.ingreso if estadia.estado == 'activa' else False)
            salida = ''
            if estadia.salida_prevista and estadia.estado == 'activa':
                dia = pytz.utc.localize(estadia.salida_prevista).astimezone(tz).date()
                salida = ('sale hoy' if dia == hoy else 'sale mañana' if dia == hoy + timedelta(days=1)
                          else f'sale el {fecha_corta(dia)}')
            resultado.append({
                'id': estadia.id,
                'mascota': mascota.name,
                'mascota_id': mascota.id,
                'emoji': mascota.emoji,
                'foto': self._foto(mascota),
                'tipo': estadia.tipo,
                'tipo_texto': estadia._tipo_texto(),
                'estado': estadia.estado,
                'lugar': estadia.lugar_id.name,
                'dueno': estadia.dueno_id.name,
                'motivo': (estadia.motivo or '').split('\n')[0][:80],
                'dias': estadia.dias_hasta_hoy,
                'salida': salida,
                'control': self._hace(estadia.ultimo_control, ahora) if estadia.ultimo_control else 'sin controles',
                'sin_control': bool(
                    estadia.estado == 'activa' and estadia.tipo == 'internacion' and ultimo and horas_control > 0
                    and ultimo + timedelta(hours=horas_control) < ahora),
                'alertas': mascota.alertas or '',
            })
        return resultado

    def _avisos(self, hoy, inicio_dia, fin_dia):
        company = self.env.company
        Aplicacion = self.env['vet.aplicacion']
        pendientes = [('company_id', '=', company.id), ('renovada', '=', False), ('no_avisar', '=', False),
                      ('proxima_fecha', '!=', False), ('mascota_id.fallecida', '=', False)]
        vencidas = Aplicacion.search_count(pendientes + [('proxima_fecha', '<', hoy), ('avisada_el', '=', False)])
        semana = Aplicacion.search_count(pendientes + [('proxima_fecha', '>=', hoy),
                                                       ('proxima_fecha', '<=', hoy + timedelta(days=7)),
                                                       ('avisada_el', '=', False)])
        cobrado = 0
        for modelo in ('vet.atencion', 'vet.internacion', 'vet.venta'):
            documentos = self.env[modelo].search([('company_id', '=', company.id),
                                                  ('factura_id.invoice_date', '=', hoy)])
            cobrado += sum(documentos.mapped('monto_cobrado'))
        manana = self.env['vet.atencion'].search_count([
            ('company_id', '=', company.id), ('estado', '=', 'reservada'),
            ('fecha_inicio', '>=', fin_dia), ('fecha_inicio', '<', fin_dia + timedelta(days=1)),
        ])
        return {
            'vacunas_vencidas': vencidas,
            'vacunas_semana': semana,
            'reponer': len(self.env['product.template']._vet_por_reponer()),
            'cobrado_hoy': format_amount(self.env, cobrado, company.currency_id),
            'turnos_manana': manana,
        }
