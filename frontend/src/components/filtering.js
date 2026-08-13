/** Las funciones del filtrado, sin componentes: si conviven en el mismo
 *  fichero, el refresco rápido de Vite deja de funcionar en toda la pantalla.
 */

/** Las personas que aparecen en una lista, para poder filtrar por ellas.
 *
 *  Sale de las propias filas y no de la plantilla entera: en una cola de
 *  decisiones, ofrecer las ciento veinte personas de la empresa cuando solo
 *  hay cuatro esperando es enseñar ciento dieciséis opciones que no hacen
 *  nada.
 */
export function peopleIn(rows, { id = 'employee', name = 'employee_name' } = {}) {
  const seen = new Map()
  for (const row of rows) {
    if (row?.[id] && !seen.has(row[id])) seen.set(row[id], row[name] ?? '—')
  }
  return [...seen.entries()]
    .map(([value, label]) => ({ value: String(value), label }))
    .sort((a, b) => a.label.localeCompare(b.label, 'es'))
}

/** Busca un texto en varios campos de una fila, sin acentos ni mayúsculas.
 *
 *  Sin `normalize`, escribir «rocio» no encuentra a «Rocío», que es
 *  precisamente lo que alguien teclea con prisa.
 */
export const matches = (needle, ...fields) => {
  const wanted = plain(needle)
  if (!wanted) return true
  return fields.some((field) => plain(field).includes(wanted))
}

const plain = (value) =>
  String(value ?? '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
