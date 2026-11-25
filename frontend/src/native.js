/** Si esta copia de la web va dentro de la aplicación de Android.
 *
 *  Se decide al compilar (`npm run android`, ver vite.config.js) y no mirando el
 *  navegador: dentro del APK la pantalla es una vista web de Android, que se
 *  parece demasiado a Chrome como para fiarse de lo que diga de sí misma.
 *
 *  Lo que cambia dentro del APK:
 *  - No se ofrece instalar: ya está instalada.
 *  - No hay Web Push: la vista web de Android no lo tiene. Los avisos al móvil
 *    del APK van por otro camino.
 *  - No se mira `version.json`: los ficheros van dentro del APK y no se ponen al
 *    día con un despliegue, así que compararlos con el servidor siempre daría
 *    «hay otra versión».
 */
export const isNativeApp = import.meta.env.VITE_NATIVE === 'android'
