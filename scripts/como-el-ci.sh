#!/usr/bin/env bash
#
# Lo mismo que corre el CI, aquí, antes de empujar.
#
# El CI de este repositorio se ha puesto rojo una y otra vez por cosas que en
# local nunca fallaban, y siempre por la misma razón: **yo comprobaba otra cosa**.
#
#   - Corría `ruff check apps/` y el CI corre `ruff check .`, que además mira
#     `config/`, `manage.py` y los scripts.
#   - Corría los linters antes del último cambio y empujaba después, así que lo
#     último que tocaba viajaba sin revisar.
#   - Y había **dos pasos que no corría nunca**: que el esquema OpenAPI compile
#     sin avisos, y que el frontend construya.
#
# Las suites en verde no dicen nada de ninguno de esos cuatro. Esto sí.
#
#     ./scripts/como-el-ci.sh
#
# Tarda lo que tarde la suite de backend --- minuto y medio --- y no levanta la
# de navegador, que el CI tampoco corre.

set -uo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API="${OTT_API_CONTAINER:-opentimetrack_api_1}"
fallos=0

paso() {
  local titulo="$1"
  shift
  printf '\n\033[1m» %s\033[0m\n' "$titulo"
  if "$@"; then
    printf '  \033[32mbien\033[0m\n'
  else
    printf '  \033[31mFALLA\033[0m\n'
    fallos=$((fallos + 1))
  fi
}

en_el_api() { podman exec "$API" "$@"; }

# --- Backend, en el mismo orden que el fichero del CI ------------------------
paso 'ruff check .' en_el_api ruff check .
paso 'ruff format --check .' en_el_api ruff format --check .
paso 'migraciones sin generar' en_el_api python manage.py makemigrations --check --dry-run
paso 'pytest' en_el_api python -m pytest -q
paso 'el esquema OpenAPI compila' en_el_api python manage.py spectacular --fail-on-warn --file /dev/null

# --- Frontend ----------------------------------------------------------------
cd "$AQUI/frontend" || exit 1
paso 'npm run lint' npm run lint
paso 'npm run i18n:check' npm run i18n:check
paso 'npm run build' npm run build

printf '\n'
if [ "$fallos" -eq 0 ]; then
  printf '\033[32mLos ocho pasos del CI, en verde.\033[0m\n'
  exit 0
fi
printf '\033[31m%d paso(s) que el CI también va a ver.\033[0m\n' "$fallos"
exit 1
