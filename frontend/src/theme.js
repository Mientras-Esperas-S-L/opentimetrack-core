import { createTheme } from '@mui/material/styles'
import { caES, esES } from '@mui/material/locale'

/** El paquete de MUI que toca a cada idioma.
 *
 *  MUI trae catalán y **no trae gallego**. Sin esta tabla, un gallego se
 *  quedaría con el paquete por defecto de MUI, que está en inglés: los
 *  `aria-label` de la paginación y los botones del buscador saldrían en un
 *  tercer idioma. Es el mismo fallo que ya se cazó en el backend ---caer al
 *  inglés en vez de al castellano--- y aquí se evita a mano.
 *
 *  Así que gallego usa el castellano para lo interno de MUI mientras nuestras
 *  propias cadenas sí van en gallego. No es lo ideal, pero es lo correcto: un
 *  producto a medias en dos idiomas de aquí se lee; en gallego e inglés, no.
 */
const PAQUETE_MUI = { es: esES, ca: caES, gl: esES }

/** «Abrir», no «Abierto».
 *
 *  MUI traduce «open» por lo que el desplegable **está**, no por lo que el
 *  botón **hace**. Solo el castellano lo tiene mal; el catalán del paquete dice
 *  «Obrir», que es correcto.
 */
const CORRECCIONES = {
  es: { components: { MuiAutocomplete: { defaultProps: { openText: 'Abrir' } } } },
  ca: {},
  gl: { components: { MuiAutocomplete: { defaultProps: { openText: 'Abrir' } } } },
}

// Un tema propio, no el azul por defecto de MUI. La idea es que la pantalla de
// fichaje se lea de un vistazo en un móvil viejo y a pleno sol: contraste alto,
// tipografía grande y un acento que distinga "dentro" de "fuera" sin depender
// solo del color.
export const buildTheme = (mode = 'light', idioma = 'es') =>
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
        // El `warning` de MUI ---#ed6c02--- da **3,11** con el texto blanco que
        // el propio MUI le pone encima en un chip relleno, y el mínimo para
        // texto normal es 4,5. Lo llevan dos estados de una corrección:
        // «esperando a la empresa» y «esperando tu respuesta», o sea los dos
        // que piden que alguien haga algo. Este ámbar da **5,26** y se
        // distingue del terracota del `secondary`, que es lo otro que hay que
        // cuidar: los dos estados no pueden parecer el mismo de un vistazo.
        //
        // En oscuro se queda el de MUI: ahí el chip pone texto casi negro
        // encima y sale a 8,29.
        warning: { main: mode === 'light' ? '#8f6400' : '#ffa726' },
        // Lo mismo les pasaba a estos dos, y no lo vio ninguna pantalla: MUI
        // les pone texto blanco encima ---su regla es ponerlo cuando el blanco
        // llega a 3--- y se quedaban en **3,68** el rojo y **3,86** el azul.
        // Estos llegan a 5,62 y 5,80. En oscuro los de MUI van bien, porque ahí
        // el texto que ponen encima es casi negro.
        error: { main: mode === 'light' ? '#c62828' : '#e57373' },
        info: { main: mode === 'light' ? '#026aa7' : '#4fc3f7' },
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
        // Un nombre largo no puede sacar la página de la pantalla.
        //
        // El modelo acepta cien caracteres en el nombre de un departamento, y
        // cien caracteres sin un solo espacio ---un código, dos nombres
        // pegados--- no tienen dónde partirse: la tarjeta se estiraba 434 px
        // más allá del borde en escritorio y 719 en el móvil, y la página
        // entera se desplazaba en horizontal.
        //
        // Va en el tema y no en la pantalla que falló porque son ocho las que
        // pintan nombres libres en tarjetas, y la novena que se añada mañana
        // nace con el mismo agujero. Mismo criterio que el paquete de idioma de
        // aquí abajo.
        //
        // `anywhere` y no `break-word`: la diferencia es que `anywhere` sí
        // reduce el ancho mínimo del contenido, que es lo que necesita un hijo
        // de un flex para encogerse de verdad. Con `break-word` el contenedor
        // sigue reservando el ancho de la palabra entera.
        MuiTypography: {
          styleOverrides: {
            root: { overflowWrap: 'anywhere' },
          },
        },
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
    PAQUETE_MUI[idioma] ?? esES,
    // Después del paquete a propósito: `createTheme` fusiona de izquierda a
    // derecha y gana el último, así que una corrección puesta antes no se
    // aplica --- me pasó con esta misma.
    CORRECCIONES[idioma] ?? {},
  )
