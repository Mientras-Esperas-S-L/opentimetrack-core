import { createTheme } from '@mui/material/styles'
import { esES } from '@mui/material/locale'

// Un tema propio, no el azul por defecto de MUI. La idea es que la pantalla de
// fichaje se lea de un vistazo en un móvil viejo y a pleno sol: contraste alto,
// tipografía grande y un acento que distinga "dentro" de "fuera" sin depender
// solo del color.
export const buildTheme = (mode = 'light') =>
  createTheme(
    {
      palette: {
        mode,
        primary: { main: mode === 'light' ? '#1b5e4a' : '#4db6a0' },
        secondary: { main: '#b0533a' },
        success: { main: '#2e7d52' },
        background:
          mode === 'light'
            ? { default: '#f6f7f5', paper: '#ffffff' }
            : { default: '#12161a', paper: '#1a2026' },
      },
      shape: { borderRadius: 10 },
      typography: {
        fontFamily: '"Inter", system-ui, -apple-system, "Segoe UI", sans-serif',
        h1: { fontSize: '2rem', fontWeight: 650, letterSpacing: '-0.02em' },
        h2: { fontSize: '1.4rem', fontWeight: 600, letterSpacing: '-0.01em' },
        button: { textTransform: 'none', fontWeight: 600 },
      },
      components: {
        MuiButton: {
          styleOverrides: {
            root: { paddingInline: 20, paddingBlock: 10 },
          },
        },
        MuiPaper: {
          styleOverrides: {
            root: { backgroundImage: 'none' },
          },
        },
      },
    },
    // El paquete de español de MUI, y no por gusto: sus componentes rotulan en
    // inglés lo que no se ve --- los `aria-label` de la paginación («Go to next
    // page») y los botones del buscador («Clear», «Open»). No se leen con los
    // ojos, así que aguantaron sin que nadie los reportara; los lee quien navega
    // con lector de pantalla o deja el ratón encima, que es exactamente la
    // persona a la que peor le viene encontrarse otro idioma.
    //
    // Va aquí y no componente a componente para que lo que se añada mañana
    // nazca traducido.
    esES,
    // Después de `esES` a propósito: `createTheme` fusiona de izquierda a
    // derecha y gana el último, así que una corrección puesta antes del paquete
    // no se aplica --- me pasó con esta misma.
    //
    // MUI traduce «open» por «Abierto», que es lo que el desplegable está, no lo
    // que el botón hace. Lo demás del paquete vale tal cual.
    { components: { MuiAutocomplete: { defaultProps: { openText: 'Abrir' } } } },
  )
