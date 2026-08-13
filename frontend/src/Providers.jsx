import { useCallback, useMemo, useState } from 'react'
import CssBaseline from '@mui/material/CssBaseline'
import { ThemeProvider } from '@mui/material/styles'
import useMediaQuery from '@mui/material/useMediaQuery'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { AuthProvider } from './context/AuthContext.jsx'
import { ColorSchemeContext } from './context/colorSchemeContext.js'
import { buildTheme } from './theme.js'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
})

/** Claro, oscuro, o lo que diga el sistema.
 *
 *  Guardado en el navegador y no en la ficha de la persona, a propósito: es una
 *  preferencia del **aparato**, como el aviso del navegador. Alguien puede
 *  querer el modo oscuro en el móvil que mira en el almacén y el claro en el
 *  ordenador de la oficina, y forzarle el mismo en los dos por sincronizar sería
 *  peor producto.
 *
 *  Por defecto, el sistema. Es lo que ya había y es lo correcto: quien se ha
 *  molestado en poner su teléfono en oscuro no tiene que volver a decirlo aquí.
 */
const STORED = 'ott.theme'
const CHOICES = ['system', 'light', 'dark']

const storedChoice = () => {
  try {
    const saved = localStorage.getItem(STORED)
    return CHOICES.includes(saved) ? saved : 'system'
  } catch {
    // Modo incógnito o almacenamiento bloqueado: se sigue el sistema y ya.
    return 'system'
  }
}

/** Shared context: theme, query cache, session. */
export default function Providers({ children }) {
  const prefersDark = useMediaQuery('(prefers-color-scheme: dark)')
  const [choice, setStored] = useState(storedChoice)

  const setChoice = useCallback((next) => {
    setStored(CHOICES.includes(next) ? next : 'system')
    try {
      localStorage.setItem(STORED, next)
    } catch {
      // Que no se pueda recordar no impide cambiarlo en esta sesión.
    }
  }, [])

  const resolved = choice === 'system' ? (prefersDark ? 'dark' : 'light') : choice
  const theme = useMemo(() => buildTheme(resolved), [resolved])
  const scheme = useMemo(() => ({ choice, resolved, setChoice }), [choice, resolved, setChoice])

  return (
    <ColorSchemeContext.Provider value={scheme}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <QueryClientProvider client={queryClient}>
          <AuthProvider>{children}</AuthProvider>
        </QueryClientProvider>
      </ThemeProvider>
    </ColorSchemeContext.Provider>
  )
}
