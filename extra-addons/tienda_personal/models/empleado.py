# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

from .comun import hoy

# Campo booleano de cada día de la semana, en el orden de date.weekday() (lunes = 0).
DIAS_SEMANA = ['trabaja_lun', 'trabaja_mar', 'trabaja_mie', 'trabaja_jue', 'trabaja_vie', 'trabaja_sab', 'trabaja_dom']

ESTADOS_HOY = [
    ('trabajando', 'Trabajando'),
    ('salio', 'Ya salió'),
    ('sin_marcar', 'Sin marcar'),
    ('falta', 'Falta'),
    ('reposo', 'Reposo'),
    ('permiso', 'Permiso'),
    ('libre', 'Día libre'),
]


class TiendaEmpleado(models.Model):
    _name = 'tienda.empleado'
    _description = 'Empleado'
    _order = 'name'

    name = fields.Char('Nombre y apellido', required=True)
    ci = fields.Char('Cédula')
    telefono = fields.Char('Teléfono')
    direccion = fields.Char('Dirección')
    puesto = fields.Char('Puesto', help='Por ejemplo: cajero, repositor, encargado.')
    sucursal_id = fields.Many2one('tienda.sucursal', string='Sucursal', required=True, index=True,
                                  default=lambda self: self.env.user.tienda_sucursal_id)
    fecha_ingreso = fields.Date('Fecha de ingreso', default=fields.Date.context_today)
    control_desde = fields.Date('Controlar asistencia desde', required=True, default=lambda self: hoy(),
                                help='Desde esta fecha el sistema marca las faltas de los días sin entrada.')
    currency_id = fields.Many2one('res.currency', string='Moneda', required=True,
                                  default=lambda self: self.env.company.currency_id)
    pago_hora = fields.Monetary('Pago por hora', required=True)
    active = fields.Boolean('Activo', default=True)
    nota = fields.Text('Notas')

    trabaja_lun = fields.Boolean('Lunes', default=True)
    trabaja_mar = fields.Boolean('Martes', default=True)
    trabaja_mie = fields.Boolean('Miércoles', default=True)
    trabaja_jue = fields.Boolean('Jueves', default=True)
    trabaja_vie = fields.Boolean('Viernes', default=True)
    trabaja_sab = fields.Boolean('Sábado', default=True)
    trabaja_dom = fields.Boolean('Domingo', default=False)

    asistencia_ids = fields.One2many('tienda.asistencia', 'empleado_id', string='Asistencia')
    reposo_ids = fields.One2many('tienda.reposo', 'empleado_id', string='Reposos')
    ajuste_ids = fields.One2many('tienda.ajuste', 'empleado_id', string='Bonos y sanciones')
    pago_ids = fields.One2many('tienda.pago', 'empleado_id', string='Pagos')

    # Datos del panel: dependen del día de hoy, por eso no se guardan.
    estado_hoy = fields.Selection(ESTADOS_HOY, string='Hoy', compute='_compute_panel')
    entrada_hoy = fields.Datetime('Entrada de hoy', compute='_compute_panel')
    horas_pendientes = fields.Float('Horas sin pagar', compute='_compute_panel')
    a_pagar = fields.Monetary('Le debo', compute='_compute_panel', search='_search_a_pagar',
                              help='Horas trabajadas sin pagar + bonos − sanciones.')
    faltas_mes = fields.Integer('Faltas del mes', compute='_compute_panel',
                                help='Faltas sin aviso en el mes actual (los reposos y permisos no cuentan).')
    corresponde_bono = fields.Boolean('Corresponde bono', compute='_compute_panel', search='_search_corresponde_bono',
                                      help='No corresponde bono a quien faltó sin aviso en el mes actual.')
    dias_sin_salida = fields.Integer('Días sin marcar salida', compute='_compute_panel')

    _sql_constraints = [
        ('pago_hora_positivo', 'CHECK(pago_hora >= 0)', 'El pago por hora no puede ser negativo.'),
    ]

    def _trabaja_el(self, fecha):
        self.ensure_one()
        return self[DIAS_SEMANA[fecha.weekday()]]

    def _reposo_en(self, fecha):
        self.ensure_one()
        return self.reposo_ids.filtered(lambda r: r.desde <= fecha <= r.hasta)[:1]

    @api.depends_context('uid')
    def _compute_panel(self):
        dia = hoy()
        inicio_mes = dia.replace(day=1)
        Asistencia = self.env['tienda.asistencia']
        for empleado in self:
            recientes = Asistencia.search([('empleado_id', '=', empleado.id), '|',
                                           ('fecha', '>=', inicio_mes), ('pagado', '=', False)])
            de_hoy = recientes.filtered(lambda a: a.fecha == dia)
            if de_hoy and de_hoy.estado == 'presente':
                empleado.estado_hoy = 'salio' if de_hoy.salida else 'trabajando'
            elif de_hoy:
                empleado.estado_hoy = de_hoy.estado
            elif empleado._reposo_en(dia):
                empleado.estado_hoy = 'reposo'
            else:
                empleado.estado_hoy = 'sin_marcar' if empleado._trabaja_el(dia) else 'libre'
            empleado.entrada_hoy = de_hoy.entrada

            trabajadas = recientes.filtered(lambda a: a.estado == 'presente' and a.salida and not a.pagado)
            ajustes = empleado.ajuste_ids.filtered(lambda a: not a.pagado)
            bonos = sum(ajustes.filtered(lambda a: a.tipo == 'bono').mapped('monto'))
            sanciones = sum(ajustes.filtered(lambda a: a.tipo == 'sancion').mapped('monto'))
            empleado.horas_pendientes = sum(trabajadas.mapped('horas'))
            empleado.a_pagar = sum(trabajadas.mapped('monto')) + bonos - sanciones
            empleado.faltas_mes = len(recientes.filtered(lambda a: a.estado == 'falta' and a.fecha >= inicio_mes))
            empleado.corresponde_bono = not empleado.faltas_mes
            empleado.dias_sin_salida = len(recientes.filtered(
                lambda a: a.estado == 'presente' and not a.salida and a.fecha < dia))

    def _buscar_en_panel(self, campo, operador, valor):
        # Pocos empleados: se calcula en Python y se devuelve la lista de ids.
        empleados = self.with_context(active_test=False).search([])
        return [('id', 'in', empleados.filtered_domain([(campo, operador, valor)]).ids)]

    def _search_a_pagar(self, operador, valor):
        return self._buscar_en_panel('a_pagar', operador, valor)

    def _search_corresponde_bono(self, operador, valor):
        return self._buscar_en_panel('corresponde_bono', operador, valor)

    def action_marcar_entrada(self):
        self.ensure_one()
        dia = hoy()
        asistencia = self.asistencia_ids.filtered(lambda a: a.fecha == dia)
        if asistencia.entrada:
            raise UserError(f'{self.name} ya marcó la entrada hoy.')
        valores = {'estado': 'presente', 'entrada': fields.Datetime.now(), 'salida': False}
        if asistencia:
            # Por ejemplo, el sistema lo había marcado como falta y llegó más tarde.
            asistencia.write(valores)
        else:
            self.env['tienda.asistencia'].create({'empleado_id': self.id, 'fecha': dia, **valores})
        return True

    def action_marcar_salida(self):
        self.ensure_one()
        asistencia = self.asistencia_ids.filtered(lambda a: a.fecha == hoy() and a.entrada)
        if not asistencia:
            raise UserError(f'{self.name} no marcó la entrada hoy.')
        if asistencia.salida:
            raise UserError(f'{self.name} ya marcó la salida hoy.')
        asistencia.salida = fields.Datetime.now()
        return True

    def action_pagar(self):
        """Junta todo lo pendiente del empleado en un pago y lo abre para revisarlo."""
        self.ensure_one()
        pago = self.pago_ids.filtered(lambda p: p.estado == 'borrador')[:1] \
            or self.env['tienda.pago'].create({'empleado_id': self.id})
        pago._cargar_pendientes()
        if not (pago.asistencia_ids or pago.ajuste_ids):
            pago.unlink()
            raise UserError(f'No hay nada pendiente de pago para {self.name}.')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Pago',
            'res_model': 'tienda.pago',
            'res_id': pago.id,
            'view_mode': 'form',
        }
