# -*- coding: utf-8 -*-
"""Crea una base de Odoo vacía como lo hace el gestor de bases de datos: español de Paraguay, país Paraguay
(moneda guaraníes, zona horaria de Asunción), usuario admin / admin y sin los datos de demostración de Odoo.

Lo usa crear_peluqueria.sh; corre con el Python del contenedor:
    docker compose exec -T web python3 - peluqueria < extra-addons/studio_bella/scripts/crear_base.py
"""
import sys

import odoo
from odoo.service import db

odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '--log-level=warn'])
nombre = sys.argv[1] if len(sys.argv) > 1 else 'peluqueria'
if nombre in db.list_dbs(force=True):
    sys.exit(f'Ya existe una base llamada "{nombre}". Elegí otro nombre o borrala antes.')
db.exp_create_database(nombre, False, 'es_PY', user_password='admin', login='admin', country_code='PY')
print(f'Base "{nombre}" creada.')
