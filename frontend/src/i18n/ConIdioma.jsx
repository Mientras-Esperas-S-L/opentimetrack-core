import { useEffect, useMemo } from 'react'
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

  useEffect(() => {
    // `changeLanguage` es asíncrono y devuelve una promesa que aquí no hace
    // falta esperar: los componentes se vuelven a pintar solos cuando i18next
    // avisa del cambio.
    if (i18next.language !== idioma) i18next.changeLanguage(idioma)
  }, [idioma])

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
      {children}
    </ThemeProvider>
  )
}
