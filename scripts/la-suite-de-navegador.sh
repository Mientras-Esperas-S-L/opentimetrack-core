#!/usr/bin/env bash
#
# La suite de navegador, con el resultado leído como es debido.
#
# Existe porque durante varias vueltas la corrí a mano así:
#
#     npx playwright test --reporter=line | tail -6
#
# y eso hace dos cosas malas a la vez. El código de salida pasa a ser el de
# `tail` ---siempre cero--- y, cuando hay varios fallos, Playwright los lista
# antes del resumen, de modo que la línea «N failed» se sale del recorte y
# desaparece. Una tanda con cinco fallos se leía como verde.
#
# Lo que lo delató no fue el resumen sino **el recuento**: 327 pruebas «en
# verde» cuando el proyecto tiene 340. Por eso este script compara el total
# contra `--list` además de mirar el código de salida.
#
# La suite tarda unos trece minutos y no puede correr a la vez que la de
# servidor: comparten la base de datos de desarrollo.
set -euo pipefail

cd "$(dirname "$0")/../frontend"

export OTT_URL="${OTT_URL:-http://localhost:3010}"
export OTT_API_URL="${OTT_API_URL:-http://localhost:8100/api}"

salida="$(mktemp -t ott-e2e-XXXXXX.log)"
trap 'rm -f "$salida"' EXIT

esperadas="$(npx playwright test --list 2>/dev/null | sed -n 's/^Total: \([0-9]*\) tests.*/\1/p')"

set +e
npx playwright test --reporter=line >"$salida" 2>&1
codigo=$?
set -e

resumen="$(grep -E '^\s+[0-9]+ (passed|failed|flaky|did not run|skipped)' "$salida" | tr -d ' ' | paste -sd' ' -)"
pasadas="$(grep -oE '^\s+[0-9]+ passed' "$salida" | grep -oE '[0-9]+' | tail -1)"
pasadas="${pasadas:-0}"

printf '\033[1m%s\033[0m\n' "${resumen:-sin resumen}"

if [ "$codigo" -ne 0 ]; then
  printf '\033[31mPlaywright salió con %d. Los fallos, arriba.\033[0m\n' "$codigo"
  grep -E '^\s+\[chromium\].*›' "$salida" | tail -20
  exit "$codigo"
fi

if [ -n "$esperadas" ] && [ "$pasadas" != "$esperadas" ]; then
  printf '\033[31m%s de %s: la tanda no está completa aunque nadie diga «failed».\033[0m\n' \
    "$pasadas" "$esperadas"
  exit 1
fi

printf '\033[32mLas %s pruebas de navegador, en verde.\033[0m\n' "$pasadas"
