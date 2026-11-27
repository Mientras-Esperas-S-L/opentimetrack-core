/** Entregar un fichero al navegador.
 *
 *  Vivía dentro de la pantalla de Informes, y hace falta en dos: quien
 *  administra saca el registro de la plantilla, y **cada persona el suyo**, que
 *  es lo que pide el art. 34.9 al decir que el registro permanece a disposición
 *  de las personas trabajadoras.
 */

import { isNativeApp } from '../native.js'

/** Guarda el blob con el nombre que eligió el servidor.
 *
 *  Revocar la URL importa aquí: estos documentos no son pequeños y la pestaña
 *  puede quedarse abierta todo el día.
 */
export function save({ blob, filename }) {
  if (isNativeApp) return saveInTheApp({ blob, filename })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

/** Dentro del APK, un enlace con `download` no hace nada: la vista web de Android
 *  no descarga. El fichero se escribe en la caché de la aplicación y se ofrece
 *  con el menú de compartir del móvil, que es desde donde se abre con el visor de
 *  PDF, se guarda en Archivos o se manda por correo.
 *
 *  En la caché y no en Descargas: así no hace falta pedir permiso de
 *  almacenamiento, y Android la vacía solo. Lo que la persona quiera conservar lo
 *  guarda ella desde el menú.
 */
async function saveInTheApp({ blob, filename }) {
  const [{ Directory, Filesystem }, { Share }] = await Promise.all([
    import('@capacitor/filesystem'),
    import('@capacitor/share'),
  ])
  const { uri } = await Filesystem.writeFile({
    path: safeName(filename),
    data: await asBase64(blob),
    directory: Directory.Cache,
  })
  try {
    await Share.share({ title: filename, files: [uri] })
  } catch {
    // Cerrar el menú sin elegir nada también llega aquí, y no es un fallo.
  }
}

/** Solo el nombre: un `../` que viniera del servidor no saca el fichero de la caché. */
const safeName = (name) => (name || 'documento').replace(/[/\\]/g, '_')

const asBase64 = (blob) =>
  new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result).split(',', 2)[1] ?? '')
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(blob)
  })
