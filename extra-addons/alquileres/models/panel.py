# -*- coding: utf-8 -*-
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

from .contrato import DIAS_AVISO_REAJUSTE, DIAS_AVISO_VENCIMIENTO
from .utiles import MESES, fecha_corta, guaranies

MESES_DEL_GRAFICO = 6


class AlquilerPanel(models.AbstractModel):
    """Los números del Panel (static/src/panel): cobranza del mes, deuda, ocupación, ganancia y lo que hay que
    atender hoy."""
    _name = 'alquiler.panel'
    _description = 'Panel de Óga'

    def _suma(self, modelo, dominio, campo):
        return self.env[modelo]._read_group(dominio, [], [f'{campo}:sum'])[0][0] or 0

    @api.model
    def datos(self):
        hoy = fields.Date.context_today(self)
        inicio_mes = hoy.replace(day=1)
        fin_mes = inicio_mes + relativedelta(months=1)
        inicio_anio = hoy.replace(month=1, day=1)
        Cuota = self.env['alquiler.cuota']

        a_cobrar = self._suma('alquiler.cuota', [('fecha_vencimiento', '>=', inicio_mes),
                                                  ('fecha_vencimiento', '<', fin_mes)], 'total')
        cobrado = self._suma('alquiler.resultado', [('tipo', '=', 'ingreso'), ('fecha', '>=', inicio_mes),
                                                     ('fecha', '<', fin_mes)], 'ingreso')
        gastos = self._suma('alquiler.gasto', [('fecha', '>=', inicio_mes), ('fecha', '<', fin_mes)], 'monto')
        vencidas = Cuota.search(Cuota._dominio_vencidas())
        unidades = self.env['alquiler.unidad'].search([])
        alquiladas = unidades.filtered(lambda u: u.estado == 'alquilada')

        indicadores = [
            {'clave': 'cobrado', 'titulo': f'Cobrado en {MESES[hoy.month - 1]}', 'valor': guaranies(cobrado),
             'detalle': f'de {guaranies(a_cobrar)} que vencen este mes',
             'progreso': round(100 * cobrado / a_cobrar) if a_cobrar else 0},
            {'clave': 'deuda', 'titulo': 'Deben', 'valor': guaranies(sum(vencidas.mapped('saldo'))),
             'detalle': self._plural(len(vencidas.contrato_id), 'inquilino atrasado', 'inquilinos atrasados'),
             'alerta': bool(vencidas)},
            {'clave': 'ocupacion', 'titulo': 'Ocupación',
             'valor': f'{round(100 * len(alquiladas) / len(unidades)) if unidades else 0} %',
             'detalle': f'{len(alquiladas)} de {len(unidades)} unidades alquiladas',
             'progreso': round(100 * len(alquiladas) / len(unidades)) if unidades else 0},
            {'clave': 'ganancia', 'titulo': f'Ganancia de {MESES[hoy.month - 1]}', 'valor': guaranies(cobrado - gastos),
             'detalle': f'cobrado menos {guaranies(gastos)} de gastos', 'alerta': cobrado - gastos < 0},
        ]
        return {
            'hoy': f'{fecha_corta(hoy)} de {hoy.year}',
            'indicadores': indicadores,
            'meses': self._meses(hoy),
            'propiedades': self._propiedades(inicio_anio),
            'atender': self._atender(hoy),
        }

    def _plural(self, cantidad, singular, plural):
        return f'{cantidad} {singular if cantidad == 1 else plural}'

    def _meses(self, hoy):
        """Cobrado y gastado en los últimos meses, para el gráfico de barras."""
        meses = []
        for atras in range(MESES_DEL_GRAFICO - 1, -1, -1):
            inicio = hoy.replace(day=1) - relativedelta(months=atras)
            fin = inicio + relativedelta(months=1)
            dominio = [('fecha', '>=', inicio), ('fecha', '<', fin)]
            meses.append({
                'mes': MESES[inicio.month - 1][:3].capitalize(),
                'cobrado': self._suma('alquiler.resultado', dominio, 'ingreso'),
                'gastos': self._suma('alquiler.resultado', dominio, 'gasto'),
            })
        tope = max([mes['cobrado'] for mes in meses] + [mes['gastos'] for mes in meses] + [1])
        for mes in meses:
            mes['alto_cobrado'] = round(100 * mes['cobrado'] / tope)
            mes['alto_gastos'] = round(100 * mes['gastos'] / tope)
            mes['cobrado_texto'] = guaranies(mes['cobrado'])
            mes['gastos_texto'] = guaranies(mes['gastos'])
        return meses

    def _propiedades(self, inicio_anio):
        filas = []
        resultado = {propiedad: (ingreso, gasto) for propiedad, ingreso, gasto in self.env['alquiler.resultado']._read_group(
            [('fecha', '>=', inicio_anio)], ['propiedad_id'], ['ingreso:sum', 'gasto:sum'])}
        for propiedad in self.env['alquiler.propiedad'].search([]):
            ingreso, gasto = resultado.get(propiedad, (0, 0))
            filas.append({
                'id': propiedad.id,
                'nombre': propiedad.name,
                'ciudad': propiedad.ciudad,
                'ocupacion': propiedad.ocupacion,
                'alquiler_mensual': guaranies(propiedad.alquiler_mensual),
                'deuda': guaranies(propiedad.deuda) if propiedad.deuda else '',
                'cobrado': guaranies(ingreso),
                'gastos': guaranies(gasto),
                'ganancia': guaranies(ingreso - gasto),
                'perdida': ingreso - gasto < 0,
            })
        return filas

    def _atender(self, hoy):
        """Lo que hay que hacer: avisos de pago, contratos que vencen, reajustes, reparaciones e interesados."""
        pendientes = []
        avisos = self.env['alquiler.cuota'].search_count([('estado', '!=', 'pagada'), ('proximo_aviso', '<=', hoy)])
        if avisos:
            pendientes.append({'icono': 'fa-whatsapp', 'color': 'success',
                               'texto': self._plural(avisos, 'aviso de pago para mandar hoy',
                                                     'avisos de pago para mandar hoy'),
                               'accion': 'alquileres.action_alquiler_avisos'})
        Contrato = self.env['alquiler.contrato']
        for contrato in Contrato.search([('estado', '=', 'vigente'), ('fecha_fin', '!=', False),
                                         ('fecha_fin', '<=', hoy + timedelta(days=DIAS_AVISO_VENCIMIENTO))],
                                        order='fecha_fin'):
            pendientes.append({'icono': 'fa-calendar-times-o', 'color': 'warning',
                               'texto': f'El contrato de {contrato.inquilino_id.name} ({contrato.unidad_id.display_name}) '
                                        f'vence el {fecha_corta(contrato.fecha_fin)}',
                               'modelo': 'alquiler.contrato', 'id': contrato.id})
        for contrato in Contrato.search([('estado', '=', 'vigente'), ('reajuste_pct', '>', 0),
                                         ('fecha_reajuste', '<=', hoy + timedelta(days=DIAS_AVISO_REAJUSTE))],
                                        order='fecha_reajuste'):
            pendientes.append({'icono': 'fa-line-chart', 'color': 'info',
                               'texto': f'Reajuste de {contrato.inquilino_id.name} el '
                                        f'{fecha_corta(contrato.fecha_reajuste)}: de {guaranies(contrato.monto)} a '
                                        f'{guaranies(contrato.monto_reajustado)}',
                               'modelo': 'alquiler.contrato', 'id': contrato.id})
        reparaciones = self.env['alquiler.mantenimiento'].search([('estado', 'in', ('nuevo', 'en_proceso'))])
        for pedido in reparaciones.sorted(lambda p: (p.prioridad != '1', p.fecha)):
            urgente = 'Urgente: ' if pedido.prioridad == '1' else ''
            pendientes.append({'icono': 'fa-wrench', 'color': 'danger' if urgente else 'secondary',
                               'texto': f'{urgente}{pedido.name} ({pedido.unidad_id.display_name})',
                               'modelo': 'alquiler.mantenimiento', 'id': pedido.id})
        interesados = self.env['alquiler.interesado'].search_count([('estado', '=', 'nuevo')])
        if interesados:
            pendientes.append({'icono': 'fa-user-plus', 'color': 'primary',
                               'texto': self._plural(interesados, 'interesado nuevo para contestar',
                                                     'interesados nuevos para contestar'),
                               'accion': 'alquileres.action_alquiler_interesado'})
        return pendientes
