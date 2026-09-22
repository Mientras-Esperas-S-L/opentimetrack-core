import { useEffect, useState } from 'react'

import { amIPlatformAdmin } from '../services/api.js'

/** Si quien mira administra la **instalación**, no una empresa.
 *
 *  Se pregunta al servidor en vez de deducirlo de la sesión: el superusuario de
 *  plataforma es el que no pertenece a ninguna empresa, y eso ni viaja en la
 *  sesión ni tiene por qué ---es un dato de la instalación, no de la persona---.
 *  Una llamada al entrar, y el menú ya sabe si enseñar la sección.
 *
 *  Devuelve `null` mientras no se sabe, para no parpadear.
 */
export function usePlatformAdmin() {
  const [esAdmin, setEsAdmin] = useState(null)

  useEffect(() => {
    let vivo = true
    amIPlatformAdmin().then((si) => {
      if (vivo) setEsAdmin(si)
    })
    return () => {
      vivo = false
    }
  }, [])

  return esAdmin
}
