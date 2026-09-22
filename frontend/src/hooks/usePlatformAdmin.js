import { useEffect, useState } from 'react'

import { useAuth } from './useAuth.js'
import { amIPlatformAdmin } from '../services/api.js'

/** Si quien mira administra la **instalación**, no una empresa.
 *
 *  Se pregunta al servidor, porque lo que hay en la sesión no basta para decir que
 *  sí. Pero **sí basta para decir que no**: quien tiene empresa no puede administrar
 *  la instalación ---eso es exactamente lo que la define---, así que a quien la
 *  tiene no se le pregunta.
 *
 *  Sin ese atajo, cada persona que solo ficha disparaba una petición a
 *  `/api/platform/me/` en cada carga y se llevaba un **403**: ruido en el registro
 *  del servidor y un error rojo en la consola de su navegador. Medido en devel el
 *  23/09/2026 con una cuenta de fichaje.
 *
 *  Devuelve `null` mientras no se sabe, para no parpadear.
 */
export function usePlatformAdmin() {
  const { session } = useAuth()
  const tieneEmpresa = Boolean(session?.tenant)
  const [respuesta, setRespuesta] = useState(null)

  useEffect(() => {
    if (tieneEmpresa) return undefined
    let vivo = true
    amIPlatformAdmin().then((si) => {
      if (vivo) setRespuesta(si)
    })
    return () => {
      vivo = false
    }
  }, [tieneEmpresa])

  //  Con empresa la respuesta se sabe sin preguntar, y se devuelve directamente en
  //  vez de escribirla en el estado: un `setState` síncrono dentro de un efecto
  //  dispara renders en cascada y el linter del proyecto lo para.
  return tieneEmpresa ? false : respuesta
}
