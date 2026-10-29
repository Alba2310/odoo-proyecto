#!/usr/bin/env bash
# Corre los tests de un módulo en una base aparte, "pruebas_<módulo>", y no en la base que se usa de verdad.
# Los tests deshacen todo lo que crean, menos los números de las secuencias de PostgreSQL (citas, recibos,
# órdenes, pedidos...): corridos en la base real, la numeración queda con saltos.
#
# Uso, desde la carpeta del proyecto y con Odoo levantado (docker compose up -d):
#   bash scripts/pruebas.sh studio_bella             -> la primera vez crea la base y después solo la actualiza
#   bash scripts/pruebas.sh alquileres
#   bash scripts/pruebas.sh autoflow_management
#   bash scripts/pruebas.sh studio_bella --nueva     -> borra la base de pruebas y la crea de cero
#
# La base de pruebas es como las reales (español de Paraguay, admin / admin, sin datos de demostración);
# los tests se arman su propia empresa y sus datos. En Windows se corre desde Git Bash o WSL.
set -euo pipefail
export MSYS_NO_PATHCONV=1  # Git Bash: que no convierta /etc/odoo/... en rutas de Windows

MODULO="${1:?Falta el módulo, por ejemplo: bash scripts/pruebas.sh studio_bella}"
BASE="pruebas_$MODULO"
# El 8079 porque el contenedor web ya usa el 8069. Solo se muestran avisos, errores y el resumen de los tests.
ODOO=(odoo -c /etc/odoo/odoo.conf -d "$BASE" --http-port=8079 --log-level=warn --log-handler=odoo.tests.result:INFO
      --test-enable --test-tags "/$MODULO" --stop-after-init)

if [ ! -d "extra-addons/$MODULO" ]; then
    echo "No existe el módulo extra-addons/$MODULO." >&2
    exit 1
fi

existe_base() {
    [ "$(docker compose exec -T db psql -U odoo -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$BASE'")" = 1 ]
}

if [ "${2:-}" = "--nueva" ] && existe_base; then
    echo "Borrando la base \"$BASE\"..."
    docker compose exec -T web odoo db -c /etc/odoo/odoo.conf drop "$BASE"
fi

if existe_base; then
    echo "Actualizando $MODULO en \"$BASE\" y corriendo los tests..."
    docker compose exec -T web "${ODOO[@]}" -u "$MODULO"
else
    echo "Creando la base \"$BASE\" (la primera vez tarda unos minutos)..."
    docker compose exec -T web python3 - "$BASE" <<'PY'
import sys

import odoo
from odoo.service import db

odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '--log-level=warn'])
db.exp_create_database(sys.argv[1], False, 'es_PY', user_password='admin', login='admin', country_code='PY')
PY
    echo "Instalando $MODULO y corriendo los tests..."
    if ! docker compose exec -T web "${ODOO[@]}" -i "$MODULO"; then
        echo "Falló algo. Si fue la instalación (no un test), volvé a crear la base con: bash scripts/pruebas.sh $MODULO --nueva" >&2
        exit 1
    fi
fi
echo "Listo: los tests pasaron."
