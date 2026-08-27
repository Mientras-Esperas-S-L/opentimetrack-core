/** Cómo se llaman en pantalla el tipo y el origen de un fichaje.
 *
 *  En su propio módulo, sin componentes: los usan la insignia de la tabla y el
 *  filtro de la barra, y un módulo que exporta componentes y datos a la vez
 *  rompe el refresco rápido de Vite. El mismo motivo por el que `useAuth`,
 *  `useSelection` y `bulk.js` viven aparte.
 *
 *  Y en un sitio, no dos: la insignia decía «Móvil» y un filtro escrito aparte
 *  habría acabado diciendo «Aplicación móvil» sin que nadie lo notara hasta
 *  buscar por una cosa y ver la otra.
 *
 *  Los rótulos van marcados con `alCatalogo` y se traducen donde se pintan: el
 *  módulo se evalúa al cargarse, cuando todavía no se sabe en qué idioma va a
 *  mirarlo nadie.
 */

import { alCatalogo } from '../i18n/index.js'

export const PUNCH_TYPES = [
  { value: 'IN', label: alCatalogo('Entrada') },
  { value: 'OUT', label: alCatalogo('Salida') },
]

export const SOURCE_LABELS = {
  WEB: alCatalogo('Web'),
  MOBILE: alCatalogo('Móvil'),
  APPLICATION: alCatalogo('App externa'),
  DELEGATED: alCatalogo('En su nombre'),
  TERMINAL: alCatalogo('Terminal'),
  ADMIN: alCatalogo('Corrección'),
  IMPORT: alCatalogo('Importado'),
}

/** Los orígenes como opciones de un desplegable, en el orden de la lista. */
export const SOURCE_OPTIONS = Object.entries(SOURCE_LABELS).map(([value, label]) => ({
  value,
  label,
}))
