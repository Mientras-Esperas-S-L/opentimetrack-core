import { createContext } from 'react'

/** Aparte del proveedor: un módulo que exporta componentes y otra cosa rompe el
 *  refresco rápido de Vite. Mismo reparto que `authContext`. */
export const ColorSchemeContext = createContext(null)
