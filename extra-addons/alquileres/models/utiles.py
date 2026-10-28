# -*- coding: utf-8 -*-
"""Textos que se repiten en avisos y recibos: guaraníes, fechas en castellano y números de WhatsApp."""
import re

try:
    from num2words import num2words
except ImportError:  # viene con Odoo; sin ella el recibo sale sin el monto en letras
    num2words = None

MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre',
         'noviembre', 'diciembre']


def guaranies(monto):
    """1500000 → 'Gs. 1.500.000'."""
    return 'Gs. ' + f'{round(monto or 0):,}'.replace(',', '.')


def fecha_corta(fecha):
    """5 de noviembre."""
    return f'{fecha.day} de {MESES[fecha.month - 1]}'


def fecha_larga(fecha):
    """5 de noviembre de 2026."""
    return f'{fecha_corta(fecha)} de {fecha.year}'


def mes_y_anio(fecha):
    """noviembre de 2026."""
    return f'{MESES[fecha.month - 1]} de {fecha.year}'


def en_letras(monto):
    """1500000 → 'un millón quinientos mil guaraníes'; 1000000 → 'un millón de guaraníes'."""
    if num2words is None:
        return ''
    texto = num2words(round(monto or 0), lang='es')
    if texto.endswith(('millón', 'millones')):
        texto += ' de'
    return f'{texto} guaraníes'


def primer_nombre(nombre):
    return (nombre or '').split(' ')[0]


def numero_whatsapp(telefono, codigo_pais='595'):
    """Número en el formato que pide wa.me: solo dígitos, con el código del país y sin el 0 de adelante.
    0981 234 567 → 595981234567; +54 9 11 1234-5678 → 5491112345678."""
    if not telefono:
        return ''
    digitos = re.sub(r'\D', '', telefono)
    if telefono.strip().startswith(('+', '00')):
        return digitos.lstrip('0')
    if digitos.startswith('0'):
        return codigo_pais + digitos[1:]
    if digitos.startswith(codigo_pais):
        return digitos
    return codigo_pais + digitos if digitos else ''
