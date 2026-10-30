#!/usr/bin/env bash
# Crea desde cero la base de Patitas, lista para usar, con una veterinaria de ejemplo.
#
# Uso, desde la carpeta del proyecto y con Odoo levantado (docker compose up -d):
#   bash extra-addons/veterinaria/scripts/crear_veterinaria.sh            -> base "veterinaria"
#   bash extra-addons/veterinaria/scripts/crear_veterinaria.sh otra_base  -> otro nombre
#
# En Windows se corre desde Git Bash o WSL.
set -euo pipefail
export MSYS_NO_PATHCONV=1  # Git Bash: que no convierta /etc/odoo/... en rutas de Windows

BASE="${1:-veterinaria}"
SCRIPTS="extra-addons/veterinaria/scripts"
ODOO=(odoo -c /etc/odoo/odoo.conf -d "$BASE" --http-port=8079 --log-level=warn)

echo "1/3 Creando la base \"$BASE\" (español de Paraguay)..."
docker compose exec -T web python3 - "$BASE" < "$SCRIPTS/crear_base.py"

echo "2/3 Instalando Patitas (tarda unos minutos)..."
docker compose exec -T web "${ODOO[@]}" -i veterinaria --without-demo=all --stop-after-init

echo "3/3 Configurando la empresa y cargando los datos de ejemplo..."
docker compose exec -T web odoo shell -c /etc/odoo/odoo.conf -d "$BASE" --http-port=8079 --log-level=warn \
    < "$SCRIPTS/configurar_base.py"

echo
echo "Listo. Entrá a http://localhost:8069/web/login?db=$BASE con usuario admin y contraseña admin."
echo "La página de turnos: http://patitas.localhost:8073/reservar (servicio patitas de docker-compose.yml)."
