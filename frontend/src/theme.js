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
        // Los tres se aclaran en oscuro, y hasta ahora solo lo hacía el
        // primero. Sobre el papel oscuro (#1a2026), el verde de «Aprobada»
        // quedaba en 3.26 de contraste y el terracota de «Aplicada sin acuerdo»
        // en 3.24 --- por debajo del 4.5 que pide la norma para texto normal, y
        // justo en los distintivos que dicen en qué estado está algo.
        //
        // Salió barriendo el contraste real en oscuro. El del terracota no lo
        // vio el barrido ---su estado no aparecía en ninguna de las pantallas
        // recorridas--- sino la cuenta, al mirar por qué el otro fallaba.
        primary: { main: mode === 'light' ? '#1b5e4a' : '#4db6a0' },
        secondary: { main: mode === 'light' ? '#b0533a' : '#e08a70' },
        success: { main: mode === 'light' ? '#2e7d52' : '#57c48c' },
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
        // La inicial de una persona, legible.
        //
        // El avatar por defecto de MUI pone texto del color del fondo de la
        // página sobre un gris medio: **1.75 de contraste en claro**, o sea la
        // letra prácticamente invisible, y 3.94 en oscuro. Es la inicial de
        // quien está trabajando ahora mismo, en la portada.
        //
        // No se vio antes porque depende del dato: con nadie fichado la lista
        // está vacía y el avatar no existe.
        MuiAvatar: {
          styleOverrides: {
            colorDefault: {
              backgroundColor: mode === 'light' ? '#1b5e4a' : '#4db6a0',
              color: mode === 'light' ? '#ffffff' : '#12161a',
              fontWeight: 600,
            },
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
