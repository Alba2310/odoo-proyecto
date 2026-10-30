# -*- coding: utf-8 -*-
"""Textos que se repiten en los mensajes de WhatsApp, los correos y el tablero."""
import re
from urllib.parse import quote

MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre',
         'noviembre', 'diciembre']
DIAS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']

# Lo que se muestra cuando la mascota no tiene foto.
EMOJIS = {
    'perro': '🐶', 'gato': '🐱', 'ave': '🐦', 'conejo': '🐰', 'roedor': '🐹', 'reptil': '🦎', 'pez': '🐟',
    'otro': '🐾',
}


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


def enlace_whatsapp(partner, texto, company):
    """Enlace wa.me que abre WhatsApp con el mensaje escrito para el contacto; vacío si no tiene teléfono."""
    numero = numero_whatsapp(partner.mobile or partner.phone, str(company.country_id.phone_code or 595))
    return f'https://wa.me/{numero}?text={quote(texto)}' if numero else False


def guaranies(monto):
    """1500000 → 'Gs. 1.500.000'."""
    return 'Gs. ' + f'{round(monto or 0):,}'.replace(',', '.')


def fecha_corta(fecha):
    """5 de noviembre."""
    return f'{fecha.day} de {MESES[fecha.month - 1]}'


def fecha_con_dia(fecha):
    """martes 5 de noviembre."""
    return f'{DIAS[fecha.weekday()]} {fecha_corta(fecha)}'


def primer_nombre(nombre):
    return (nombre or '').split(' ')[0]


def edad_texto(nacimiento, hoy):
    """Edad para leer de un vistazo: '3 años y 2 meses', '5 meses', '12 días'."""
    if not nacimiento or nacimiento > hoy:
        return ''
    meses = (hoy.year - nacimiento.year) * 12 + hoy.month - nacimiento.month - (hoy.day < nacimiento.day)
    anios, meses = divmod(meses, 12)
    if not anios and not meses:
        dias = (hoy - nacimiento).days
        return f'{dias} día{"s" if dias != 1 else ""}'
    partes = []
    if anios:
        partes.append(f'{anios} año{"s" if anios != 1 else ""}')
    if meses:
        partes.append(f'{meses} mes{"es" if meses != 1 else ""}')
    return ' y '.join(partes)


def lista_con_y(partes):
    """['a', 'b', 'c'] → 'a, b y c'."""
    partes = [parte for parte in partes if parte]
    if len(partes) <= 1:
        return ''.join(partes)
    return ', '.join(partes[:-1]) + ' y ' + partes[-1]
