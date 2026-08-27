import { Fragment, useEffect, useMemo } from 'react'
import CssBaseline from '@mui/material/CssBaseline'
import { ThemeProvider } from '@mui/material/styles'

import { useAuth } from '../hooks/useAuth.js'
import { buildTheme } from '../theme.js'
import i18next, { normalizar } from './index.js'

/** Pone toda la aplicación en el idioma de quien la está usando.
 *
 *  Tiene que ir **dentro** de `AuthProvider` y por eso existe como componente
 *  aparte: el idioma sale de la sesión, y hasta que la sesión no está resuelta
 *  no se sabe cuál es. Antes el tema se construía fuera, donde no hay sesión
 *  ninguna.
 *
 *  El orden de preferencia es el mismo que ya aplicaba `api.js` para la cabecera
 *  `Accept-Language`, y eso es lo importante: si el idioma de las pantallas y el
 *  de las respuestas del servidor se calcularan por separado, acabarían
 *  discrepando y una pantalla en catalán enseñaría un error en castellano.
 *
 *  1. Lo que haya elegido la persona (`user.locale`).
 *  2. Lo que haya declarado su empresa (`tenant.language`).
 *  3. Lo que diga el navegador.
 *
 *  Sin sesión ---la pantalla de entrar--- manda el navegador, que es lo único
 *  que hay. Es también lo correcto: quien todavía no ha entrado no tiene
 *  empresa.
 */
export default function ConIdioma({ modo, children }) {
  const { session } = useAuth()

  const idioma = normalizar(
    session?.user?.locale || session?.tenant?.language || navigator.language,
  )

  // Se fija **antes** de pintar, no en un efecto. Lo que sale en el primer
  // paso ---el mes de una cabecera, la fecha de una fila--- se escribe con el
  // idioma que hubiera en ese momento, y un efecto corre después: la pantalla
  // salía entera en catalán con «Agosto de 2026» encima.
  //
  // Los recursos van en el paquete, así que esto no espera a ninguna descarga.
  if (i18next.language !== idioma) i18next.changeLanguage(idioma)

  // El idioma entra en las dependencias porque decide el paquete de MUI, que
  // vive dentro del tema. Sin esto, cambiar de idioma dejaría la paginación y
  // el buscador en el anterior.
  const theme = useMemo(() => buildTheme(modo, idioma), [modo, idioma])

  useEffect(() => {
    // Para el navegador y para quien navegue con lector de pantalla: sin el
    // atributo correcto, un lector castellano pronuncia el catalán con las
    // reglas del castellano. Y decide la partición de palabras.
    document.documentElement.lang = idioma
  }, [idioma])

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      {/* La `key` remonta la aplicación al cambiar de idioma, y hace falta:
          `useTranslation` solo repinta a quien lo usa, y las fechas salen de
          `format.js`, que no es un componente y no puede usarlo. Sin esto,
          cambiar el idioma en caliente dejaba los meses en el anterior hasta
          recargar. Cuesta el estado de la pantalla ---un filtro puesto, un
          formulario a medias--- y pasa una vez, cuando alguien lo cambia a
          propósito. */}
      <Fragment key={idioma}>{children}</Fragment>
    </ThemeProvider>
  )
}
