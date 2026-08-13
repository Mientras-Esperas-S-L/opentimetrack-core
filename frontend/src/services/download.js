/** Entregar un fichero al navegador.
 *
 *  Vivía dentro de la pantalla de Informes, y hace falta en dos: quien
 *  administra saca el registro de la plantilla, y **cada persona el suyo**, que
 *  es lo que pide el art. 34.9 al decir que el registro permanece a disposición
 *  de las personas trabajadoras.
 */

/** Guarda el blob con el nombre que eligió el servidor.
 *
 *  Revocar la URL importa aquí: estos documentos no son pequeños y la pestaña
 *  puede quedarse abierta todo el día.
 */
export function save({ blob, filename }) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
