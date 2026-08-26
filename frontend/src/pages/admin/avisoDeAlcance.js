/** Qué decirle a quien administra sobre las responsables que no llevan nada.
 *
 *  La misma lista significa dos cosas opuestas según el momento de la empresa, y
 *  el aviso decía siempre la primera:
 *
 *  - Mientras **nadie** lleve ningún departamento no se ha decidido nada, así que
 *    una responsable lee a toda la plantilla. Es la concesión deliberada del
 *    diseño: una empresa recién dada de alta no puede tener una responsable que
 *    no ve a nadie, porque lo que se hace entonces es apagar el alcance, no
 *    descubrir los departamentos.
 *  - En cuanto alguien lleva uno, llevar ninguno pasa a ser una respuesta y no un
 *    silencio: esa responsable lee **solo su propio registro**. Le ocurre a quien
 *    acaba de ceder su departamento a un compañero, y hasta la vuelta 84 lo que
 *    le ocurría era lo contrario --- se llevaba la empresa entera.
 *
 *  Cuál de los dos es lo dice el servidor en `department_scoping_in_use`. Aquí no
 *  se recalcula: dos copias de una regla son una que se queda atrás.
 */

/** El aviso, o `null` si no hay nada que avisar.
 *
 *  @param {{name: string}[]} sueltos  responsables sin ningún departamento
 *  @param {boolean} alcanceEnUso      si alguien de la empresa ya lleva alguno
 *  @returns {{severity: 'info'|'warning', text: string} | null}
 */
export function avisoDeAlcance(sueltos, alcanceEnUso) {
  if (!sueltos?.length) return null

  const una = sueltos.length === 1
  const consecuencia = alcanceEnUso
    ? una
      ? 'así que solo ve su propio registro'
      : 'así que solo ven su propio registro'
    : una
      ? 'así que ve a toda la empresa'
      : 'así que ven a toda la empresa'

  return {
    // Que nadie vea a nadie es un estorbo; que alguien vea de más es un riesgo.
    severity: alcanceEnUso ? 'info' : 'warning',
    text: una
      ? `${sueltos[0].name} no lleva ningún departamento, ${consecuencia}.`
      : `${sueltos.length} responsables no llevan ningún departamento, ${consecuencia}: ${sueltos
          .map((m) => m.name)
          .join(', ')}.`,
  }
}
