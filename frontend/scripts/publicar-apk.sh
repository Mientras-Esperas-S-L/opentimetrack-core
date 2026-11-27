#!/usr/bin/env bash
# Compila, firma y (con --publicar) publica una versión del APK.
#
#   OTT_ANDROID_FIRMA=/ruta/firma.properties \
#   APK_PUBLIC_URL=https://descargas.example.com/descargas \
#   APK_UPLOAD=/ruta/subir.sh \
#     scripts/publicar-apk.sh [--publicar]
#
# La API a la que entra el APK sale de VITE_API_URL (o de .env.android.local), como
# con `npm run android`. NOMBRE (por defecto `ott`) es el nombre de los ficheros.
#
# Deja en dist-apk/:
#   <NOMBRE>-<versión>.apk   el APK firmado de esta versión
#   <NOMBRE>.apk             el mismo, con nombre fijo, para repartir el enlace
#   <NOMBRE>.json            {version, apk, sha256, fecha}: lo que el APK instalado
#                            consulta para saber si hay una versión nueva
#
# Con --publicar llama a APK_UPLOAD con cada fichero, primero los APK y al final el
# .json: así ningún móvil ve anunciada una versión cuyo APK aún no está. Cómo se
# sube depende de cada instalación, y por eso no está aquí. Ver
# docs/aplicacion-android.md.
set -euo pipefail
cd "$(dirname "$0")/.."

PUBLICAR=no
[ "${1:-}" = "--publicar" ] && PUBLICAR=si
NOMBRE=${NOMBRE:-ott}
: "${APK_PUBLIC_URL:?falta APK_PUBLIC_URL, la carpeta pública donde quedan los ficheros}"
: "${OTT_ANDROID_FIRMA:?falta OTT_ANDROID_FIRMA, el fichero con la firma de publicación}"
[ -r "$OTT_ANDROID_FIRMA" ] || { echo "no se puede leer $OTT_ANDROID_FIRMA" >&2; exit 1; }
if [ "$PUBLICAR" = si ]; then
  : "${APK_UPLOAD:?falta APK_UPLOAD, la orden que sube un fichero}"
fi
JAVA_HOME=${JAVA_HOME_21:-${JAVA_HOME:-}}
export ANDROID_HOME=${ANDROID_HOME:-$HOME/Android/Sdk}
APK_PUBLIC_URL=${APK_PUBLIC_URL%/}

VERSION=$(date -u +%Y.%m.%d.%H%M)
echo "==> versión $VERSION"

# 1. La web, compilada para dentro del APK y copiada al proyecto de Android.
APK_VERSION=$VERSION APK_VERSION_URL=$APK_PUBLIC_URL/$NOMBRE.json \
  npx vite build --mode android
npx cap sync android

# 2. El APK firmado. Si la firma falta, Gradle lo saca sin firmar y aquí se para.
(cd android && ./gradlew -q ${JAVA_HOME:+-Dorg.gradle.java.home="$JAVA_HOME"} \
  assembleRelease "-PottVersion=$VERSION")
APK=android/app/build/outputs/apk/release/app-release.apk
[ -f "$APK" ] || { echo "no ha salido el APK firmado (¿falta la firma?)" >&2; exit 1; }
APKSIGNER=$(ls "$ANDROID_HOME"/build-tools/*/apksigner | sort -V | tail -1)
"$APKSIGNER" verify "$APK" || { echo "el APK no pasa apksigner verify" >&2; exit 1; }

# 3. Lo que se publica.
OUT=dist-apk
rm -rf "$OUT" && mkdir -p "$OUT"
cp "$APK" "$OUT/$NOMBRE-$VERSION.apk"
cp "$APK" "$OUT/$NOMBRE.apk"
SHA=$(sha256sum "$OUT/$NOMBRE.apk" | cut -d' ' -f1)
printf '{"version":"%s","apk":"%s-%s.apk","sha256":"%s","fecha":"%s"}\n' \
  "$VERSION" "$NOMBRE" "$VERSION" "$SHA" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$OUT/$NOMBRE.json"
ls -la "$OUT"

if [ "$PUBLICAR" = si ]; then
  for f in "$NOMBRE-$VERSION.apk" "$NOMBRE.apk" "$NOMBRE.json"; do
    "$APK_UPLOAD" "$OUT/$f"
  done
  curl -fsS "$APK_PUBLIC_URL/$NOMBRE.json" && echo "==> publicado: $APK_PUBLIC_URL/$NOMBRE.apk ($VERSION)"
fi
