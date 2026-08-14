/** Errores que significan «lo que tienes en pantalla ya no es verdad».
 *
 *  La mayoría de los rechazos del servidor son sobre lo que acabas de escribir:
 *  falta un campo, la fecha no vale, el turno se pisa con otro. Se enseña el
 *  mensaje y ya está, que para eso están escritos con cuidado.
 *
 *  Unos pocos son distintos: dicen que **otra persona llegó antes**. Y ahí
 *  enseñar el mensaje no basta, porque la fila sigue en la lista. Quien lo lee
 *  vuelve a pulsar, recibe el mismo error, y la pantalla le sigue mintiendo
 *  hasta que recarga a mano.
 *
 *  Salió al mirar qué hace la interfaz con los códigos del servidor: las
 *  treinta y cuatro mutaciones del producto hacen `onError: setError` y ninguna
 *  refresca. El caso llegó el mismo día que el bloqueo de las decisiones
 *  concurrentes ---antes de aquello, las dos personas se creían las dos que
 *  habían resuelto, que era peor---.
 *
 *  La lista es corta a propósito. Refrescar en cualquier 409 sería más simple y
 *  traería la lista entera cada vez que a alguien le falta un campo, que es la
 *  mayoría de las veces.
 */

/** Códigos que significan que alguien resolvió esto antes que tú. */
const YA_NO_ES_TUYO = new Set([
  // Ausencias y correcciones: aprobar, rechazar o retirar algo ya resuelto.
  'already_resolved',
  // Recuperaciones de vacaciones del art. 38.3.
  'already_decided',
  // Un turno reasignado a quien ya tenía otro ese día.
  'already_rostered',
  // La corrección salió del estado en que estaba mientras la mirabas.
  'not_awaiting_the_employee',
])

export const laVistaEstaCaducada = (error) => YA_NO_ES_TUYO.has(error?.code)

/** Para un `onError`: enseña el error y, si hace falta, vuelve a pedir los datos.
 *
 *  Se usa así, y el orden importa: primero se guarda el error para que la
 *  persona lea por qué, y después se refresca. Al revés, la lista se recarga y
 *  el mensaje aparece sobre una pantalla que ya ha cambiado sola.
 */
export const alFallar = (setError, refrescar) => (error) => {
  setError(error)
  if (laVistaEstaCaducada(error)) refrescar()
}
