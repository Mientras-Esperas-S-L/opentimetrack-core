/** De la ruta al artículo de ayuda que le toca.
 *
 *  `/panel/personas` → `personas`, `/mi-jornada` → `mi-jornada`, la raíz → `fichar`.
 *
 *  Sin tabla de correspondencias: una tabla se queda vieja en cuanto alguien añade
 *  una pantalla y nadie se entera, mientras que aquí lo peor que pasa es que el
 *  artículo no exista todavía ---y entonces el cajón se abre por el índice y lo dice.
 *
 *  Vive en su propio fichero y no en `AppShell` porque el linter para un fichero que
 *  exporta un componente y además otra cosa: rompe la recarga en caliente.
 */
export function temaDeAyuda(pathname) {
  const trozos = (pathname || '/').split('/').filter(Boolean)
  if (trozos.length === 0) return 'fichar'
  return trozos[trozos.length - 1]
}
