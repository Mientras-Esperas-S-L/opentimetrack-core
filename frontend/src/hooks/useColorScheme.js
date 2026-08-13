import { useContext } from 'react'

import { ColorSchemeContext } from '../context/colorSchemeContext.js'

/** El tema elegido y cómo cambiarlo.
 *
 *  Devuelve `{ choice, resolved, setChoice }`. `choice` es lo que la persona
 *  pidió --- `system`, `light` o `dark` --- y `resolved` es lo que se está
 *  pintando de verdad, que con `system` depende del sistema operativo. Los dos,
 *  porque el interruptor tiene que enseñar lo elegido y el resto de la interfaz
 *  necesita saber lo aplicado.
 */
export function useColorScheme() {
  const context = useContext(ColorSchemeContext)
  if (!context) throw new Error('useColorScheme must be used inside Providers')
  return context
}
