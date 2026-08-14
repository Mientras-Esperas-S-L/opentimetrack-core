import { useCallback, useEffect, useMemo, useState } from 'react'

import {
  getMe,
  onSessionLost,
  setPreferredLanguage,
  signIn as apiSignIn,
  signOut as apiSignOut,
  tokens,
} from '../services/api.js'
import { AuthContext } from './authContext.js'

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)
  //: No se pudo comprobar la sesión, y **no** porque no valga.
  //:
  //: Con el testigo bueno y el servidor devolviendo 429, la aplicación se
  //: rendía y pintaba el formulario de entrada: se le pedía la contraseña a
  //: quien tenía la sesión perfectamente viva, y volver a entrar también le
  //: daba 429. En la vuelta 6 se arregló que el testigo ya no se borrara, pero
  //: el resultado que veía la persona era el mismo.
  const [unreachable, setUnreachable] = useState(null)

  // A stored token is not proof of a valid session: it may have expired, or the
  // person may have been deactivated. It gets checked against the server once.
  useEffect(() => {
    let cancelled = false

    /** Si la respuesta significa «esta sesión ya no vale».
     *
     *  Solo eso borra el testigo. Antes lo borraba **cualquier** fallo, y la
     *  diferencia se ve cuando algo va mal por otro motivo: un 429 al abrir la
     *  aplicación, un 502 del balanceador mientras se despliega, el wifi que
     *  parpadea. En los tres casos la sesión estaba viva y el producto mandaba
     *  a la persona a teclear su contraseña otra vez.
     *
     *  Salió probando el cuadrante: el propio banco de pruebas agotó las mil
     *  peticiones por hora de la cuenta y la pantalla se volvió el formulario
     *  de entrada, sin decir por qué. Detrás de un NAT de oficina eso es un
     *  martes cualquiera.
     */
    const sesionRechazada = (error) => error?.status === 401 || error?.status === 403

    const restore = async () => {
      if (!tokens.access) {
        setLoading(false)
        return
      }

      // Tres intentos con espera creciente. Un tropiezo pasajero se arregla
      // solo y nadie se entera, que es como debería haber sido siempre.
      let ultimo = null
      for (let intento = 0; intento < 3; intento += 1) {
        try {
          const data = await getMe()
          if (!cancelled) {
            setPreferredLanguage(data)
            setSession(data)
            setUnreachable(null)
            setLoading(false)
          }
          return
        } catch (error) {
          ultimo = error
          if (sesionRechazada(error)) {
            tokens.clear()
            ultimo = null
            break
          }
          if (intento === 2) break
          await new Promise((listo) => setTimeout(listo, 400 * 2 ** intento))
          if (cancelled) return
        }
      }
      // Se agotaron los intentos sin que nadie dijera que la sesión no vale.
      if (!cancelled && ultimo) setUnreachable(ultimo)

      // Se acabaron los intentos sin que el servidor dijera que la sesión no
      // vale. El testigo se queda donde está: recargar puede funcionar, y
      // borrarlo garantiza que no.
      if (!cancelled) setLoading(false)
    }

    restore()
    return () => {
      cancelled = true
    }
  }, [])

  // Cuando el servidor da la sesión por muerta, la pantalla tiene que
  // enterarse. Sin esto, `tokens.clear()` vaciaba el almacén y aquí no cambiaba
  // nada: la aplicación seguía pintando el panel y su consulta seguía pidiendo
  // cada minuto, con un 401 cada vez. Ni se arreglaba sola ni llevaba a entrar.
  //
  // Se registra en un efecto sin dependencias, una vez: es un aviso del
  // interceptor, que vive fuera de React.
  useEffect(() => {
    onSessionLost(() => setSession(null))
    return () => onSessionLost(null)
  }, [])

  const signIn = useCallback(async (credentials) => {
    const data = await apiSignIn(credentials)
    setPreferredLanguage(data)
    setSession({ user: data.user, tenant: data.tenant })
    return data
  }, [])

  const signOut = useCallback(async () => {
    await apiSignOut()
    setSession(null)
  }, [])

  const value = useMemo(
    () => ({ session, loading, unreachable, signIn, signOut, setSession }),
    [session, loading, unreachable, signIn, signOut],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
