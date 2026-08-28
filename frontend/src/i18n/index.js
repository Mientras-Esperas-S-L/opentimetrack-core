/** El idioma de la interfaz.
 *
 *  Hasta ahora esto no existía. El backend tiene catálogos de castellano,
 *  catalán y gallego, y llegaban a los correos y a los errores de la API; las
 *  pantallas seguían en castellano pasara lo que pasara. Una empresa catalana
 *  veía su producto a medias traducido, que es peor que verlo entero en un
 *  idioma.
 *
 *  ## La clave es la cadena en castellano
 *
 *  No `people.filters.showInactive` sino «Ver también las bajas». Dos razones,
 *  y la segunda pesa más:
 *
 *  1. Lo que falta cae al castellano solo, sin configurar nada, porque la clave
 *     **es** el castellano. Es exactamente lo que hace el backend, donde lo no
 *     traducido cae a `LANGUAGE_CODE` y no al inglés de los `msgid`. Que las dos
 *     mitades del producto se degraden igual no es casualidad, es la condición
 *     para que un catálogo a medias sea utilizable.
 *  2. El código de esta aplicación se lee como prosa a propósito. Cambiar
 *     `<Typography>Esta empresa no tiene permisos configurados…</Typography>`
 *     por `<Typography>{t('leaveTypes.empty.none')}</Typography>` destruiría lo
 *     único que hace que estas pantallas se puedan revisar leyéndolas.
 *
 *  El precio: editar el castellano huérfana su traducción en silencio. Es el
 *  mismo precio que paga gettext en el backend, y se paga con la misma moneda
 *  ---una comprobación que compara el catálogo con el código---.
 *
 *  ## Los dos separadores, apagados
 *
 *  `keySeparator` y `nsSeparator` van a `false` y no es opcional. Por defecto
 *  i18next parte la clave por el punto y por los dos puntos, así que «Fichaje
 *  registrado. Puedes cerrar.» se leería como el espacio de nombres «Fichaje
 *  registrado» buscando la clave « Puedes cerrar», y devolvería un fragmento o
 *  la cadena entera sin traducir según el día.
 */

import i18next from 'i18next'
import { initReactI18next } from 'react-i18next'

import ca from './locales/ca.json'
import gl from './locales/gl.json'

/** Los que tienen catálogo. El castellano no aparece porque **es** las claves. */
export const IDIOMAS = ['es', 'ca', 'gl']

/** Los que se pueden elegir, con su nombre.
 *
 *  Más que `IDIOMAS`: el inglés no tiene catálogo de pantalla pero sí de
 *  servidor ---los mensajes se escriben en inglés y el catálogo los traduce---
 *  así que quien lo elige recibe el original en los correos y en los errores.
 *
 *  **Cada uno con su propio nombre**, y por eso no pasan por `t()`: quien viene
 *  a esta lista puede no entender el idioma en el que está la pantalla ---es
 *  justo por eso por lo que viene--- y «Inglés» no le dice nada a quien busca
 *  «English».
 *
 *  Euskera, francés, portugués y alemán siguen fuera. El euskera llegó a tener
 *  catálogo y se retiró: iba incompleto ---faltaban los párrafos largos de
 *  derecho laboral--- y medio idioma en un producto que explica obligaciones
 *  legales no es medio bueno, es confuso.
 *
 *  Aquí y no en cada pantalla: estaba escrita dos veces, en los ajustes de la
 *  empresa y en la ficha de cada persona, y al arreglar el criterio en una se
 *  quedó la otra diciendo «Inglés». Dos copias de una lista divergen; la
 *  pregunta no es si, es cuándo.
 */
export const IDIOMAS_QUE_SE_OFRECEN = [
  ['es', 'Español'],
  ['ca', 'Català'],
  ['gl', 'Galego'],
  ['en', 'English'],
]

export const POR_DEFECTO = 'es'

/** El código corto, que es con lo que trabaja i18next.
 *
 *  Llega `ca`, pero también puede llegar `ca-ES` de `navigator.language` o de
 *  lo que un día guarde el backend. Sin esto, `ca-ES` no encuentra catálogo y
 *  cae al castellano teniendo la traducción delante.
 */
export const normalizar = (codigo) => {
  const corto = String(codigo || '')
    .toLowerCase()
    .split(/[-_]/)[0]
  return IDIOMAS.includes(corto) ? corto : POR_DEFECTO
}

i18next.use(initReactI18next).init({
  lng: POR_DEFECTO,
  fallbackLng: POR_DEFECTO,
  resources: {
    // El castellano no lleva recursos: la clave ya es el texto, y i18next
    // devuelve la clave cuando no encuentra traducción. Poner un catálogo
    // castellano sería mantener dos veces la misma cadena para que digan lo
    // mismo.
    es: { translation: {} },
    ca: { translation: ca },
    gl: { translation: gl },
  },
  keySeparator: false,
  nsSeparator: false,
  interpolation: {
    // React ya escapa lo que pinta. Dejar el escapado de i18next encima
    // convierte cualquier apóstrofo o comilla de un nombre propio en `&#39;`
    // dentro del texto.
    escapeValue: false,
  },
  returnEmptyString: false,
  // Una traducción vacía no puede ganarle a la clave. Es el mismo fallo que ya
  // salió en el backend, donde una forma plural sin rellenar devolvía «» en vez
  // de caer a nada: gettext con una forma vacía no cae al original.
})

/** Mete una cadena en el catálogo sin traducirla todavía.
 *
 *  Los rótulos que viven en un mapa de constantes ---`{ADD: 'Añadir un fichaje
 *  que falta'}`--- se escriben lejos de donde se pintan, y ahí arriba no hay
 *  `t()` que valga: el mapa se evalúa una vez, al cargar el módulo, cuando
 *  todavía no se sabe en qué idioma va a mirarlo nadie. Traducirlo ahí lo
 *  congelaría en el idioma del arranque.
 *
 *  Así que la cadena se marca aquí y se traduce en el punto de uso, con `t()`.
 *  Esto no hace nada ---devuelve lo que le dan--- y aun así es necesario: es lo
 *  que hace que la comprobación de catálogos encuentre la cadena en el código,
 *  y lo que distingue «pendiente de traducir» de «traducida en otro sitio».
 *
 *  Es `gettext_noop` del backend, con otro nombre.
 */
export const alCatalogo = (cadena) => cadena

/** Con qué idioma escribe el navegador las fechas y las horas.
 *
 *  Estaba en nueve sitios como `'es-ES'` fijo, así que una pantalla traducida
 *  al catalán seguía diciendo «agosto de 2026» y «Lunes, 25 Ago». La mitad
 *  traducida se ve, pero la mitad que no cambia se ve más: pasa por descuido y
 *  no por «esto todavía no está».
 *
 *  Se lee en cada llamada, no se guarda: cambiar de idioma no recarga la
 *  página, y un valor calculado al arrancar se quedaría en el de entonces.
 */
export const localeDeFechas = () => `${normalizar(i18next.language)}-ES`

export default i18next
