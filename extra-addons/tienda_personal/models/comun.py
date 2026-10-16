# -*- coding: utf-8 -*-
from datetime import datetime

import pytz

# La tienda está en Paraguay: "hoy" y las horas de entrada y salida se miden en esta zona,
# sin importar la zona horaria del usuario o del servidor.
ZONA_HORARIA = pytz.timezone('America/Asuncion')


def hoy():
    return datetime.now(ZONA_HORARIA).date()


def fecha_local(momento):
    """Fecha en Paraguay de un datetime de Odoo (guardado en UTC, sin zona)."""
    return pytz.utc.localize(momento).astimezone(ZONA_HORARIA).date()
