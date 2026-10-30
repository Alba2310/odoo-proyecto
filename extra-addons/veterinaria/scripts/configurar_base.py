# -*- coding: utf-8 -*-
"""Deja lista una base de Patitas para Paraguay y carga una veterinaria de ejemplo.

Se corre una sola vez, con la base creada en español (Paraguay) y el módulo instalado SIN los datos de
demostración de Odoo:

    docker compose exec -T web odoo shell -d veterinaria --no-http < extra-addons/veterinaria/scripts/configurar_base.py

Hace esto:
* Empresa "Veterinaria Patitas" en Fernando de la Mora, en guaraníes, con el ícono como logo y su horario.
* IVA 10 % y 5 % incluidos en el precio, como impuestos por defecto (el plan contable genérico de Odoo trae uno
  de 15 % que acá se archiva).
* Datos de ejemplo, con fechas relativas a hoy: servicios, vacunas y productos con stock, cuatro profesionales,
  lugares de internación y hotel, diez dueños con sus mascotas, la historia de cada una (consultas, vacunas, baños,
  pesos), un internado y una perra en el hotel, la sala de espera de hoy, turnos de mañana, ventas de mostrador
  y pedidos a proveedores. Se cargan una sola vez: si ya hay mascotas, no se repiten.
"""
import base64
from datetime import datetime, time, timedelta

import pytz

from odoo import Command, fields
from odoo.tools import file_open

admin = env.ref('base.user_admin')
env = env(user=admin.id, context=dict(env.context, lang='es_PY', tz='America/Asuncion'))
company = env.company
paraguay = env.ref('base.py')
horario = env.ref('veterinaria.horario_patitas')

with file_open('veterinaria/static/description/icon.png', 'rb') as icono:
    logo = base64.b64encode(icono.read())
company.write({
    'name': 'Veterinaria Patitas',
    'street': 'Av. Mariscal López 2450',
    'city': 'Fernando de la Mora',
    'country_id': paraguay.id,
    'phone': '021 500 321',
    'mobile': '0981 000 100',
    'email': 'hola@patitas.example.com',
    'logo': logo,
    'account_fiscal_country_id': paraguay.id,
    'account_price_include': 'tax_included',
    'resource_calendar_id': horario.id,
    'vet_url_reserva': 'http://patitas.localhost:8073/reservar',
})
# La página de inicio del administrador es el tablero "Hoy en Patitas".
admin.write({'tz': 'America/Asuncion', 'lang': 'es_PY', 'action_id': env.ref('veterinaria.action_vet_tablero').id})
env['stock.warehouse'].search([('company_id', '=', company.id)], limit=1).name = 'Patitas'
env['res.lang']._lang_get('es_PY').week_start = '1'

# Al instalar Facturación, el plan contable genérico deja la moneda en dólares.
# Se puede cambiar mientras no haya asientos contables.
guaranies = env.ref('base.PYG')
if company.currency_id != guaranies:
    guaranies.active = True
    company.currency_id = guaranies

# IVA: se copian los impuestos del plan genérico para quedarse con sus cuentas contables.
Tax = env['account.tax'].with_context(active_test=False)
if not Tax.search([('company_id', '=', company.id), ('name', '=', 'IVA 10 %')]):
    for uso in ('sale', 'purchase'):
        modelo = Tax.search([('company_id', '=', company.id), ('type_tax_use', '=', uso), ('amount', '=', 15)],
                            limit=1)
        impuestos = {}
        for tasa in (10, 5):
            grupo = env['account.tax.group'].search([('company_id', '=', company.id), ('name', '=', f'IVA {tasa} %')],
                                                    limit=1)
            if not grupo:
                grupo = env['account.tax.group'].create({
                    'name': f'IVA {tasa} %', 'country_id': paraguay.id, 'company_id': company.id,
                })
            impuestos[tasa] = modelo.copy({
                'name': f'IVA {tasa} %',
                'description': f'IVA {tasa} %',
                'invoice_label': f'IVA {tasa} %',
                'amount': tasa,
                'price_include_override': 'tax_included',
                'tax_group_id': grupo.id,
                'country_id': paraguay.id,
            })
        campo = 'account_sale_tax_id' if uso == 'sale' else 'account_purchase_tax_id'
        company[campo] = impuestos[10]
    Tax.search([('company_id', '=', company.id), ('amount', '=', 15)]).active = False

IVA = {tasa: Tax.search([('company_id', '=', company.id), ('name', '=', f'IVA {tasa} %'),
                         ('type_tax_use', '=', 'sale')], limit=1) for tasa in (10, 5)}
IVA_COMPRAS = {tasa: Tax.search([('company_id', '=', company.id), ('name', '=', f'IVA {tasa} %'),
                                 ('type_tax_use', '=', 'purchase')], limit=1) for tasa in (10, 5)}

if env['vet.mascota'].search_count([]):
    env.cr.commit()
    print('Patitas: la base ya tenía mascotas; no se cargaron datos de ejemplo.')
else:
    TZ = pytz.timezone('America/Asuncion')
    ahora = fields.Datetime.now()
    hoy = pytz.utc.localize(ahora).astimezone(TZ).date()
    stock = env['stock.warehouse'].search([('company_id', '=', company.id)], limit=1).lot_stock_id

    def momento(dias, hora, minuto=0):
        """Día (contado desde hoy) y hora de Asunción, en UTC sin zona como lo guarda Odoo."""
        local = TZ.localize(datetime.combine(hoy + timedelta(days=dias), time(hora, minuto)))
        return local.astimezone(pytz.utc).replace(tzinfo=None)

    def habil(dias):
        """El mismo día o el siguiente que abre (los domingos está cerrado)."""
        while (hoy + timedelta(days=dias)).weekday() == 6:
            dias += 1
        return dias

    # Servicios y productos

    def producto(nombre, precio, categoria, iva=10, stock_inicial=0, **valores):
        plantilla = env['product.template'].create({
            'name': nombre,
            'list_price': precio,
            'standard_price': round(precio * 0.55, -3),
            'categ_id': env.ref(f'veterinaria.categoria_{categoria}').id,
            'taxes_id': [Command.set(IVA[iva].ids)],
            'supplier_taxes_id': [Command.set(IVA_COMPRAS[iva].ids)],
            **valores,
        })
        if stock_inicial:
            env['stock.quant'].with_context(inventory_mode=True).create({
                'product_id': plantilla.product_variant_id.id,
                'location_id': stock.id,
                'inventory_quantity': stock_inicial,
            }).action_apply_inventory()
        return plantilla.product_variant_id

    perro = env.ref('veterinaria.especie_perro')
    gato = env.ref('veterinaria.especie_gato')
    conejo = env.ref('veterinaria.especie_conejo')
    perros = [Command.set(perro.ids)]
    gatos = [Command.set(gato.ids)]
    perros_y_gatos = [Command.set((perro | gato).ids)]
    servicio = {'type': 'service'}
    con_stock = {'type': 'consu', 'is_storable': True}

    consulta = producto('Consulta general', 120000, 'consultorio', vet_area='consultorio', vet_duracion=30,
                        vet_reserva_online=True, **servicio)
    control = producto('Control', 60000, 'consultorio', vet_area='consultorio', vet_duracion=20,
                       vet_reserva_online=True, **servicio)
    urgencia = producto('Consulta de urgencia', 200000, 'consultorio', vet_area='consultorio', vet_duracion=30,
                        **servicio)
    ecografia = producto('Ecografía', 180000, 'consultorio', vet_area='consultorio', vet_duracion=40, **servicio)
    castracion = producto('Castración', 450000, 'consultorio', vet_area='consultorio', vet_duracion=90, **servicio)
    producto('Limpieza dental', 350000, 'consultorio', vet_area='consultorio', vet_duracion=60, **servicio)

    antirrabica = producto('Vacuna antirrábica', 60000, 'vacunas', iva=5, stock_inicial=25, vet_area='consultorio',
                           vet_duracion=15, vet_reserva_online=True, vet_especie_ids=perros_y_gatos,
                           vet_aplicacion='vacuna', vet_dias_refuerzo=365, vet_stock_minimo=10, vet_stock_maximo=40,
                           **con_stock)
    sextuple = producto('Vacuna séxtuple', 110000, 'vacunas', iva=5, stock_inicial=12, vet_area='consultorio',
                        vet_duracion=15, vet_reserva_online=True, vet_especie_ids=perros, vet_aplicacion='vacuna',
                        vet_dias_refuerzo=365, vet_stock_minimo=5, vet_stock_maximo=20, **con_stock)
    triple_felina = producto('Vacuna triple felina', 120000, 'vacunas', iva=5, stock_inicial=6,
                             vet_area='consultorio', vet_duracion=15, vet_reserva_online=True, vet_especie_ids=gatos,
                             vet_aplicacion='vacuna', vet_dias_refuerzo=365, vet_stock_minimo=4, vet_stock_maximo=12,
                             **con_stock)
    producto('Vacuna tos de las perreras', 95000, 'vacunas', iva=5, stock_inicial=5, vet_area='consultorio',
             vet_duracion=15, vet_reserva_online=True, vet_especie_ids=perros, vet_aplicacion='vacuna',
             vet_dias_refuerzo=365, **con_stock)
    desparasitacion = producto('Desparasitación interna (comprimido)', 35000, 'vacunas', iva=5, stock_inicial=30,
                               vet_area='consultorio', vet_duracion=10, vet_reserva_online=True,
                               vet_especie_ids=perros_y_gatos, vet_aplicacion='desparasitacion_interna',
                               vet_dias_refuerzo=90, **con_stock)
    pipeta = producto('Pipeta antipulgas', 65000, 'vacunas', iva=5, stock_inicial=15,
                      vet_aplicacion='desparasitacion_externa', vet_dias_refuerzo=30, vet_stock_minimo=6,
                      vet_stock_maximo=20, **con_stock)

    bano_chico = producto('Baño perro chico', 60000, 'estetica', vet_area='estetica', vet_duracion=60,
                          vet_reserva_online=True, vet_especie_ids=perros, **servicio)
    producto('Baño perro grande', 90000, 'estetica', vet_area='estetica', vet_duracion=90, vet_reserva_online=True,
             vet_especie_ids=perros, **servicio)
    bano_corte = producto('Baño y corte', 130000, 'estetica', vet_area='estetica', vet_duracion=120,
                          vet_reserva_online=True, vet_especie_ids=perros, **servicio)
    bano_gato = producto('Baño de gato', 80000, 'estetica', vet_area='estetica', vet_duracion=60,
                         vet_reserva_online=True, vet_especie_ids=gatos, **servicio)
    unas = producto('Corte de uñas', 20000, 'estetica', vet_area='estetica', vet_duracion=15, vet_reserva_online=True,
                    vet_especie_ids=perros_y_gatos, **servicio)
    producto('Deslanado', 85000, 'estetica', vet_area='estetica', vet_duracion=60, vet_reserva_online=True,
             vet_especie_ids=perros, **servicio)

    dia_internacion = producto('Día de internación', 150000, 'internacion', vet_area='internacion', **servicio)
    dia_hotel = producto('Día de hotel', 70000, 'internacion', vet_area='internacion', **servicio)
    company.write({'vet_producto_internacion_id': dia_internacion.id, 'vet_producto_hotel_id': dia_hotel.id})

    alimento_perro = producto('Alimento perro adulto 15 kg', 380000, 'alimentos', stock_inicial=8,
                              vet_stock_minimo=3, vet_stock_maximo=12, **con_stock)
    alimento_cachorro = producto('Alimento cachorro 3 kg', 120000, 'alimentos', stock_inicial=6, vet_stock_minimo=2,
                                 vet_stock_maximo=8, **con_stock)
    alimento_gato = producto('Alimento gato adulto 1,5 kg', 75000, 'alimentos', stock_inicial=2, vet_stock_minimo=4,
                             vet_stock_maximo=12, **con_stock)
    arena = producto('Arena sanitaria 4 kg', 45000, 'alimentos', stock_inicial=10, **con_stock)
    collar = producto('Collar antipulgas', 85000, 'accesorios', stock_inicial=5, **con_stock)
    producto('Shampoo antipulgas', 55000, 'accesorios', stock_inicial=4, **con_stock)
    producto('Correa', 45000, 'accesorios', stock_inicial=6, **con_stock)
    amoxicilina = producto('Amoxicilina 500 mg x 10 comprimidos', 40000, 'farmacia', iva=5, stock_inicial=12,
                           **con_stock)
    meloxicam = producto('Meloxicam x 10 comprimidos', 35000, 'farmacia', iva=5, stock_inicial=1, vet_stock_minimo=3,
                         vet_stock_maximo=10, **con_stock)
    suero = producto('Suero fisiológico 500 ml', 18000, 'farmacia', iva=5, stock_inicial=20, **con_stock)

    # Profesionales y lugares

    def profesional(nombre, atiende, puesto, matricula=False):
        return env['hr.employee'].create({
            'name': nombre, 'vet_atiende': atiende, 'vet_matricula': matricula, 'job_title': puesto,
            'resource_calendar_id': horario.id, 'tz': 'America/Asuncion',
        })

    laura = profesional('Dra. Laura Giménez', 'consultorio', 'Veterinaria', 'MP 1284')
    marcos = profesional('Dr. Marcos Duarte', 'consultorio', 'Veterinario', 'MP 2211')
    romina = profesional('Romina Acosta', 'estetica', 'Peluquera canina')
    diego = profesional('Diego Ortiz', 'estetica', 'Peluquero canino')

    Lugar = env['vet.lugar']
    jaula_1 = Lugar.create({'name': 'Jaula 1', 'tipo': 'internacion', 'sequence': 1})
    jaula_2 = Lugar.create({'name': 'Jaula 2', 'tipo': 'internacion', 'sequence': 2})
    Lugar.create({'name': 'Jaula 3', 'tipo': 'internacion', 'sequence': 3})
    Lugar.create({'name': 'Gatera', 'tipo': 'internacion', 'nota': 'Para gatos', 'sequence': 4})
    Lugar.create({'name': 'Box de aislamiento', 'tipo': 'internacion', 'nota': 'Para enfermedades contagiosas',
                  'sequence': 5})
    canil_1 = Lugar.create({'name': 'Canil 1', 'tipo': 'hotel', 'nota': 'Para perros grandes', 'sequence': 10})
    canil_2 = Lugar.create({'name': 'Canil 2', 'tipo': 'hotel', 'sequence': 11})
    canil_3 = Lugar.create({'name': 'Canil 3', 'tipo': 'ambos', 'sequence': 12})

    # Dueños y mascotas

    def dueno(nombre, numero, email=False):
        return env['res.partner'].create({'name': nombre, 'mobile': f'0981 000 1{numero:02d}', 'email': email,
                                          'city': 'Fernando de la Mora', 'country_id': paraguay.id,
                                          'customer_rank': 1})

    def raza(xml_id):
        return env.ref(f'veterinaria.raza_{xml_id}').id

    def mascota(nombre, persona, especie, sexo, nacimiento_dias, raza_id=False, **valores):
        return env['vet.mascota'].create({
            'name': nombre, 'dueno_id': persona.id, 'especie_id': especie.id, 'sexo': sexo, 'raza_id': raza_id,
            'fecha_nacimiento': hoy - timedelta(days=nacimiento_dias), **valores,
        })

    ana = dueno('Ana Benítez', 1, 'ana.benitez@example.com')
    carlos = dueno('Carlos Ríos', 2)
    majo = dueno('María José Fernández', 3, 'majo.fernandez@example.com')
    jorge = dueno('Jorge Villalba', 4)
    laura_ortiz = dueno('Laura Ortiz', 5, 'laura.ortiz@example.com')
    pedro = dueno('Pedro Cabrera', 6)
    sofia = dueno('Sofía Martínez', 7, 'sofia.martinez@example.com')
    diego_acuna = dueno('Diego Acuña', 8)
    gabriela = dueno('Gabriela Sosa', 9, 'gabriela.sosa@example.com')
    ramon = dueno('Ramón Duarte', 10)

    toby = mascota('Toby', ana, perro, 'macho', 1700, raza('perro_caniche'), color='Blanco', castrado=True,
                   alimentacion='Alimento de perro adulto chico')
    michi = mascota('Michi', ana, gato, 'hembra', 1100, raza('gato_comun'), color='Atigrada gris', castrado=True)
    rocky = mascota('Rocky', carlos, perro, 'macho', 2500, raza('perro_pitbull'), color='Atigrado',
                    alertas='Muerde: usar bozal', alimentacion='Alimento de perro adulto')
    luna = mascota('Luna', majo, perro, 'hembra', 2200, raza('perro_golden'), color='Dorado', castrado=True,
                   microchip='600123000045123')
    simba = mascota('Simba', majo, gato, 'macho', 2950, raza('gato_persa'), color='Naranja', castrado=True,
                    alertas='Se estresa: manejar con toalla')
    nala = mascota('Nala', jorge, perro, 'hembra', 3300, raza('perro_ovejero'), color='Negro y fuego',
                   alergias='Alérgica a la penicilina.')
    coco = mascota('Coco', laura_ortiz, perro, 'macho', 1400, raza('perro_shih_tzu'), color='Blanco y marrón')
    firulais = mascota('Firulais', pedro, perro, 'macho', 3800, raza('perro_mestizo'), color='Marrón',
                       alergias='Alérgico a la dipirona. Artrosis en la cadera.')
    pelusa = mascota('Pelusa', pedro, conejo, 'hembra', 500, raza('conejo_enano'), color='Gris')
    milo = mascota('Milo', sofia, gato, 'macho', 120, raza('gato_siames'))
    max_ = mascota('Max', diego_acuna, perro, 'macho', 110, raza('perro_labrador'), color='Chocolate',
                   alimentacion='Alimento de cachorro, 4 veces por día')
    kiara = mascota('Kiara', gabriela, perro, 'hembra', 4100, raza('perro_yorkshire'), castrado=True,
                    alertas='Cardíaca: no sedar sin consultar')
    thor = mascota('Thor', ramon, perro, 'macho', 2300, raza('perro_rottweiler'), color='Negro y fuego',
                   castrado=True, alertas='Nervioso con otros perros')

    # Atenciones: la historia de cada mascota, cobrada el día que se atendió.

    Atencion = env['vet.atencion'].with_context(vet_sin_horario=True)

    def atencion(animal, dias, hora, quien, productos, estado='cobrada', minuto=0, pagos=None, proximas=None,
                 **valores):
        inicio = valores.get('fecha_inicio') or momento(dias, hora, minuto)
        nueva = Atencion.create({
            'mascota_id': animal.id,
            'area': 'estetica' if quien in (romina, diego) else 'consultorio',
            'profesional_id': quien.id,
            'fecha_inicio': inicio,
            'linea_ids': [Command.create({'producto_id': p.id, 'lote': f'L{p.id:03d}-{(hoy.year - 2000)}'
                                          if p.vet_aplicacion else False}) for p in productos],
            **valores,
        })
        if estado in ('lista', 'cobrada'):
            nueva.write({'estado': 'lista', 'llegada': inicio - timedelta(minutes=10), 'inicio_atencion': inicio,
                         'fin_atencion': inicio + timedelta(minutes=nueva.duracion or 30)})
            nueva._vet_registrar_aplicaciones()
            # Los cachorros se vacunan cada tres semanas: la fecha de la próxima dosis se corrige a mano.
            for aplicacion in nueva.aplicacion_ids:
                if proximas and aplicacion.producto_id in proximas:
                    aplicacion.proxima_fecha = hoy + timedelta(days=proximas[aplicacion.producto_id])
        if estado == 'cobrada':
            total = nueva.total
            nueva._vet_cobrar(pagos(total) if pagos else {'efectivo': total}, fecha=hoy + timedelta(days=dias))
        return nueva

    def mixto(total):
        return {'efectivo': round(total * 0.4, -3), 'tarjeta': total - round(total * 0.4, -3)}

    def tarjeta(total):
        return {'tarjeta': total}

    def transferencia(total):
        return {'transferencia': total}

    # Toby: las vacunas anuales ya se le vencieron y le toca la desparasitación esta semana.
    atencion(toby, -400, 10, laura, antirrabica | sextuple, peso=7.6, temperatura=38.4, motivo='Vacunas anuales',
             diagnostico='Sano. Vacunas al día.')
    atencion(toby, -120, 16, marcos, consulta | amoxicilina, peso=7.9, temperatura=39.1, motivo='Se rasca la oreja',
             anamnesis='Hace tres días que se rasca la oreja derecha y sacude la cabeza.',
             examen='Oído derecho con secreción marrón y mal olor. Resto normal.',
             diagnostico='Otitis externa derecha', tratamiento='Limpieza del oído en la consulta.',
             indicaciones='Gotas óticas 4 gotas cada 12 horas por 7 días.\nAmoxicilina 1/2 comprimido cada 12 horas '
                          'por 7 días.', proximo_control=hoy - timedelta(days=110), pagos=tarjeta)
    atencion(toby, -85, 9, laura, desparasitacion, peso=8.1, motivo='Desparasitación')
    atencion(toby, -60, 9, romina, bano_corte, estetica_pedido='Corte cachorro, orejas largas',
             estetica_observaciones='Tenía nudos detrás de las orejas.')
    atencion(toby, -30, 9, romina, bano_corte | unas, estetica_pedido='Corte cachorro', pagos=transferencia)

    # Michi: la triple felina vence en una semana.
    atencion(michi, -358, 11, laura, triple_felina | antirrabica, peso=3.9, motivo='Vacunas anuales')
    atencion(michi, -200, 15, diego, bano_gato)

    # Rocky: llegó de urgencia hace dos días y quedó internado.
    atencion(rocky, -25, 17, marcos, pipeta, peso=21.8)
    consulta_rocky = atencion(
        rocky, -2, 17, marcos, urgencia | ecografia, peso=21.3, temperatura=39.6, frecuencia_cardiaca=120,
        frecuencia_respiratoria=32, condicion_corporal='3', motivo='Vómitos y diarrea con sangre',
        anamnesis='Desde ayer vomita y tiene diarrea con sangre. No quiere comer. Comió algo en la calle.',
        examen='Deshidratación moderada, mucosas secas, dolor abdominal leve.',
        diagnostico='Gastroenteritis hemorrágica. Deshidratación moderada.',
        tratamiento='Suero subcutáneo y antiemético en la consulta.', pagos=mixto)

    # Luna y Simba
    atencion(luna, -200, 10, laura, antirrabica | sextuple, peso=29.5, motivo='Vacunas anuales')
    atencion(simba, -300, 11, marcos, triple_felina, peso=5.2, motivo='Vacuna anual')
    atencion(simba, -90, 15, diego, bano_gato | unas, estetica_observaciones='Se puso nervioso, se usó la toalla.')

    # Nala: dermatitis, con control en unos días.
    atencion(nala, -100, 10, laura, antirrabica, peso=31.2)
    atencion(nala, -10, 16, laura, consulta, peso=30.4, temperatura=38.7, motivo='Se lame las patas',
             anamnesis='Hace dos semanas que se lame las patas delanteras. Cambiaron de alimento hace un mes.',
             examen='Enrojecimiento entre los dedos de las patas delanteras. Sin parásitos visibles.',
             diagnostico='Dermatitis alérgica (posible alergia alimentaria).',
             indicaciones='Volver al alimento anterior.\nBaños con shampoo medicado cada 3 días.\nNo usar '
                          'antibióticos con penicilina (es alérgica).',
             proximo_control=hoy + timedelta(days=4), pagos=tarjeta)

    # Coco: viene a la peluquería todos los meses.
    atencion(coco, -30, 10, diego, bano_corte, estetica_pedido='Corte bien cortito, por el calor')
    atencion(coco, -200, 14, marcos, antirrabica | sextuple, peso=6.8)

    # Firulais: perro mayor con artrosis.
    atencion(firulais, -40, 15, marcos, consulta | meloxicam, peso=18.6, temperatura=38.5, motivo='Le cuesta '
             'levantarse', examen='Dolor a la manipulación de la cadera. Crepitación.',
             diagnostico='Artrosis de cadera', indicaciones='Meloxicam 1 comprimido por día con comida, por 10 días.'
                                                          '\nCaminatas cortas. Evitar escaleras.',
             proximo_control=hoy - timedelta(days=10))
    atencion(pelusa, -15, 11, marcos, control, peso=1.8, motivo='Control general', diagnostico='Sana')

    # Max y Milo: cachorros, con sus pesos y sus primeras vacunas.
    atencion(max_, -70, 10, laura, consulta | desparasitacion, peso=4.2, motivo='Primera consulta',
             diagnostico='Cachorro sano', proximas={desparasitacion: 20})
    atencion(max_, -63, 10, laura, sextuple, peso=5.1, proximas={sextuple: -42})
    atencion(max_, -42, 10, laura, sextuple, peso=8.4, proximas={sextuple: -21})
    atencion(max_, -21, 10, laura, sextuple | control, peso=11.6, proximas={sextuple: habil(1)})
    atencion(milo, -30, 16, marcos, consulta | triple_felina, peso=0.9, motivo='Primera consulta',
             diagnostico='Gatito sano', proximas={triple_felina: -9})

    # Kiara: cardíaca, con su antirrábica al día.
    atencion(kiara, -330, 9, laura, antirrabica, peso=2.6)
    atencion(kiara, -60, 9, laura, consulta | ecografia, peso=2.5, temperatura=38.3, frecuencia_cardiaca=140,
             motivo='Tos de noche', examen='Soplo cardíaco a la auscultación.',
             diagnostico='Soplo cardíaco grado II', indicaciones='Control en dos meses. No sedar sin consultar.',
             proximo_control=hoy, pagos=tarjeta)

    # Thor: castrado hace cinco meses; la antirrábica se le venció hace unos días.
    atencion(thor, -370, 10, marcos, antirrabica | sextuple, peso=41.0)

    # Internaciones y hotel

    Estadia = env['vet.internacion']

    def cobrar_estadia(estadia, dias_egreso, hora_egreso, pagos=None):
        estadia.write({'estado': 'alta', 'egreso': momento(dias_egreso, hora_egreso)})
        estadia._vet_cobrar(pagos(estadia.total) if pagos else {'efectivo': estadia.total},
                            fecha=hoy + timedelta(days=dias_egreso))

    thor_castracion = Estadia.create({
        'tipo': 'internacion', 'mascota_id': thor.id, 'lugar_id': jaula_2.id, 'profesional_id': marcos.id,
        'ingreso': momento(-150, 8), 'motivo': 'Castración', 'plan': 'Antibiótico y analgésico cada 12 horas.',
        'linea_ids': [Command.create({'producto_id': castracion.id, 'fecha': hoy - timedelta(days=150)}),
                      Command.create({'producto_id': amoxicilina.id, 'fecha': hoy - timedelta(days=150)})],
    })
    cobrar_estadia(thor_castracion, -148, 17, pagos=tarjeta)
    coco_hotel = Estadia.create({
        'tipo': 'hotel', 'mascota_id': coco.id, 'lugar_id': canil_3.id, 'ingreso': momento(-45, 10),
        'motivo': 'Vacaciones de la familia', 'pertenencias': 'Su cama y su alimento.',
    })
    cobrar_estadia(coco_hotel, -40, 17, pagos=transferencia)

    rocky_internado = Estadia.create({
        'tipo': 'internacion', 'mascota_id': rocky.id, 'lugar_id': jaula_1.id, 'profesional_id': marcos.id,
        'atencion_id': consulta_rocky.id, 'ingreso': momento(-2, 18), 'motivo': consulta_rocky.diagnostico,
        'plan': 'Suero fisiológico 500 ml cada 12 h.\nAmoxicilina 1 comprimido cada 12 h.\nAyuno 24 h; después '
                'dieta blanda en poca cantidad.',
        'pertenencias': 'Collar y correa.',
        'linea_ids': [Command.create({'producto_id': suero.id, 'cantidad': 3, 'fecha': hoy - timedelta(days=1)}),
                      Command.create({'producto_id': amoxicilina.id, 'fecha': hoy - timedelta(days=1)})],
    })
    controles = [
        (-2, 20, 39.6, 21.3, 'muy_decaido', 'nada', 'Suero 500 ml. Antiemético.', 'Vomitó una vez.'),
        (-1, 8, 39.2, False, 'decaido', 'nada', 'Suero 500 ml. Amoxicilina.', 'Sin vómitos a la noche.'),
        (-1, 14, 38.9, False, 'decaido', 'nada', '', 'Toma agua de a poco.'),
        (-1, 20, 38.8, 21.0, 'decaido', 'poco', 'Suero 500 ml. Amoxicilina.', 'Comió un poco de dieta blanda.'),
        (0, 8, 38.7, False, 'bien', 'poco', 'Amoxicilina.', 'Movió la cola cuando lo saludamos.'),
    ]
    for dias, hora, temperatura, peso, animo, comio, medicacion, observaciones in controles:
        if momento(dias, hora) <= ahora:
            env['vet.control'].create({
                'internacion_id': rocky_internado.id, 'fecha': momento(dias, hora), 'temperatura': temperatura,
                'peso': peso, 'animo': animo, 'comio': comio, 'medicacion': medicacion,
                'observaciones': observaciones, 'orino': True, 'defeco': dias < 0,
            })

    luna_hotel = Estadia.create({
        'tipo': 'hotel', 'mascota_id': luna.id, 'lugar_id': canil_2.id, 'ingreso': momento(-1, 10),
        'salida_prevista': momento(3, 18), 'motivo': 'Los dueños viajan a Encarnación.',
        'alimentacion': 'Su alimento: 2 tazas a la mañana y 2 a la noche.',
        'pertenencias': 'Cama, 3 kg de su alimento y un juguete de soga.',
    })
    env['vet.control'].create({'internacion_id': luna_hotel.id, 'fecha': momento(-1, 19), 'animo': 'bien',
                               'comio': 'bien', 'observaciones': 'Jugó en el patio y se adaptó bien.'})
    Estadia.create({
        'tipo': 'hotel', 'mascota_id': thor.id, 'lugar_id': canil_1.id, 'estado': 'reservada',
        'ingreso': momento(5, 9), 'salida_prevista': momento(9, 18), 'motivo': 'Viaje de los dueños',
    })

    # Hoy: la sala de espera. Lo que ya pasó hoy, terminado; lo que viene, reservado.
    atencion(coco, 0, 0, romina, bano_corte, estado='lista', estetica_pedido='Corte cortito',
             estetica_observaciones='Tenía unas garrapatas: le pusimos pipeta.', fecha_inicio=ahora - timedelta(hours=2))
    kiara_hoy = Atencion.create({
        'mascota_id': kiara.id, 'profesional_id': laura.id, 'fecha_inicio': ahora - timedelta(minutes=20),
        'motivo': 'Control cardiológico', 'linea_ids': [Command.create({'producto_id': control.id})],
    })
    kiara_hoy.write({'estado': 'en_curso', 'llegada': ahora - timedelta(minutes=30),
                     'inicio_atencion': ahora - timedelta(minutes=20)})
    env['vet.atencion'].create({'mascota_id': firulais.id, 'origen': 'sin_turno',
                                'motivo': 'Cojea de la pata trasera', 'llegada': ahora - timedelta(minutes=10)})
    media_hora = timedelta(minutes=30)
    for horas, animal, quien, productos, motivo in (
            (1, nala, laura, control, 'Control de la dermatitis'),
            (2, pelusa, romina, unas, False),
            (3, simba, diego, bano_gato, False),
            (4, thor, marcos, antirrabica, 'Antirrábica vencida')):
        cuando = ahora + timedelta(hours=horas)
        cuando = cuando - timedelta(minutes=cuando.minute % 30, seconds=cuando.second,
                                    microseconds=cuando.microsecond) + media_hora
        if pytz.utc.localize(cuando).astimezone(TZ).date() == hoy:
            Atencion.create({
                'mascota_id': animal.id, 'profesional_id': quien.id, 'fecha_inicio': cuando, 'motivo': motivo,
                'area': 'estetica' if quien in (romina, diego) else 'consultorio',
                'linea_ids': [Command.create({'producto_id': productos.id})],
            })

    # Mañana (o el próximo día que abre) y la semana que viene.
    manana = habil(1)
    for dias, hora, minuto, animal, quien, productos, origen, motivo in (
            (manana, 9, 0, toby, laura, desparasitacion | antirrabica | sextuple, 'recepcion', 'Vacunas atrasadas'),
            (manana, 10, 30, michi, laura, triple_felina, 'internet', 'Le toca la vacuna'),
            (manana, 10, 0, max_, laura, sextuple, 'recepcion', 'Tercera dosis'),
            (manana, 15, 0, toby, romina, bano_chico | unas, 'internet', False),
            (habil(manana + 3), 16, 0, firulais, marcos, control, 'recepcion', 'Control de la artrosis'),
            (habil(manana + 5), 9, 30, milo, marcos, triple_felina, 'recepcion', 'Segunda dosis')):
        Atencion.create({
            'mascota_id': animal.id, 'profesional_id': quien.id, 'fecha_inicio': momento(dias, hora, minuto),
            'area': 'estetica' if quien in (romina, diego) else 'consultorio', 'origen': origen,
            'motivo': motivo, 'linea_ids': [Command.create({'producto_id': p.id}) for p in productos],
        })

    # Ventas de mostrador
    Venta = env['vet.venta']
    for dias, persona, lineas, pagos in (
            (-3, None, [(alimento_perro, 1), (pipeta, 2)], tarjeta),
            (-1, ana, [(arena, 2), (alimento_gato, 1)], None),
            (0, None, [(collar, 1)], transferencia)):
        valores = {'fecha': min(momento(dias, 11), ahora),
                   'linea_ids': [Command.create({'producto_id': p.id, 'cantidad': c}) for p, c in lineas]}
        if persona:
            valores['dueno_id'] = persona.id
        venta = Venta.create(valores)
        venta._vet_cobrar(pagos(venta.total) if pagos else {'efectivo': venta.total},
                          fecha=hoy + timedelta(days=dias))

    # Compras: un pedido ya recibido y otro esperando la mercadería.
    Partner = env['res.partner']
    agrovet = Partner.create({'name': 'Distribuidora Agrovet S.A.', 'is_company': True, 'supplier_rank': 1,
                              'phone': '021 600 700', 'city': 'Asunción', 'country_id': paraguay.id})
    alimentos_py = Partner.create({'name': 'Alimentos para Mascotas PY', 'is_company': True, 'supplier_rank': 1,
                                   'phone': '021 650 800', 'city': 'San Lorenzo', 'country_id': paraguay.id})
    for producto_proveedor, proveedor in ((antirrabica, agrovet), (sextuple, agrovet), (triple_felina, agrovet),
                                          (meloxicam, agrovet), (pipeta, agrovet), (alimento_perro, alimentos_py),
                                          (alimento_gato, alimentos_py), (alimento_cachorro, alimentos_py)):
        producto_proveedor.product_tmpl_id.seller_ids = [Command.create({
            'partner_id': proveedor.id, 'price': producto_proveedor.standard_price, 'delay': 3,
        })]

    def pedido(proveedor, lineas, recibir):
        orden = env['purchase.order'].create({
            'partner_id': proveedor.id,
            'order_line': [Command.create({'product_id': p.id, 'product_qty': cantidad,
                                           'price_unit': p.standard_price}) for p, cantidad in lineas],
        })
        orden.button_confirm()
        if recibir:
            for recepcion in orden.picking_ids:
                for movimiento in recepcion.move_ids:
                    movimiento.quantity = movimiento.product_uom_qty
                recepcion.move_ids.picked = True
                recepcion.with_context(skip_sms=True, skip_backorder=True).button_validate()
        return orden

    pedido(alimentos_py, [(alimento_perro, 4), (alimento_cachorro, 4)], recibir=True)
    pedido(agrovet, [(triple_felina, 6), (meloxicam, 10)], recibir=False)

    env.cr.commit()
    print('Patitas: base configurada con los datos de ejemplo.')
    print('Mascotas:', env['vet.mascota'].search_count([]), '· Atenciones:', env['vet.atencion'].search_count([]),
          '· Facturas:', env['account.move'].search_count([('move_type', '=', 'out_invoice')]),
          '· Vacunas para avisar:', env['vet.aplicacion'].search_count([
              ('renovada', '=', False), ('proxima_fecha', '<=', hoy + timedelta(days=30))]))
