/** La hora del servidor, en la pantalla.
 *
 *  El reloj que se enseña al fichar no puede ser el del dispositivo. Todo el
 *  producto se apoya en que la hora la pone el servidor —es lo que hace que el
 *  registro valga como prueba— y enseñar al lado un reloj que dice otra cosa
 *  porque el móvil va cinco minutos adelantado invita justo a la duda que el
 *  diseño quiere cerrar.
 *
 *  No hace falta pedir nada: toda respuesta HTTP trae su cabecera `Date`. De
 *  ahí sale el desfase entre los dos relojes, y el de pared se pinta corrigiendo
 *  el del navegador con él.
 *
 *  Resolución de un segundo, que es la de la cabecera. Sobra para un reloj que
 *  se mira, y no se usa para nada que se guarde: lo que se guarda lo sella el
 *  servidor con su propia hora.
 */

let drift = 0
let known = false

/** Apunta el desfase a partir de la cabecera `Date` de una respuesta. */
export function noteServerTime(header) {
  if (!header) return
  const server = Date.parse(header)
  if (Number.isNaN(server)) return
  const seen = server - Date.now()
  // Un salto pequeño es el redondeo al segundo de la cabecera y la latencia;
  // corregir por eso haría temblar el reloj. Solo se ajusta lo que importa.
  if (!known || Math.abs(seen - drift) > 2000) {
    drift = seen
    known = true
  }
}

/** Ahora, según el servidor. */
export const serverNow = () => new Date(Date.now() + drift)

/** Un instante local, dicho en hora de servidor. Pura: la usan los componentes
 *  durante el render, donde leer el reloj directamente estaría prohibido. */
export const serverAt = (localMillis) => new Date(localMillis + drift)

/** Si ya hemos hablado con el servidor alguna vez. Antes de eso no se enseña
 *  un reloj: más vale un hueco que una hora inventada. */
export const serverClockReady = () => known
