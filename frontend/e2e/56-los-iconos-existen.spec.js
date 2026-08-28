/** Que todo icono de MUI que se importa exista de verdad.
 *
 *  Dos veces en cuatro días. Un icono que no existe no falla al escribirlo ni
 *  al guardar: Vite devuelve un 500 al pedir el módulo, React no monta, y lo
 *  que se ve es **una pantalla en blanco** o un overlay que tapa el formulario.
 *  El mensaje que lo explica está dentro del cuerpo de esa respuesta, que no
 *  mira nadie, así que las dos veces se fueron varias hipótesis antes de llegar
 *  a él.
 *
 *  La lección estaba escrita ---la 252--- y volvió a pasar. Una lección que se
 *  repite deja de ser un recordatorio y pasa a ser un guard: escribirla otra vez
 *  con más énfasis no cambia nada, ejecutarla sí.
 *
 *  Sin navegador: es leer el código y mirar el disco.
 */

import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { expect, test } from '@playwright/test'

const ICONOS = 'node_modules/@mui/icons-material'

const ficheros = (dir) =>
  readdirSync(dir).flatMap((nombre) => {
    const ruta = join(dir, nombre)
    if (statSync(ruta).isDirectory()) return ficheros(ruta)
    return /\.jsx?$/.test(nombre) ? [ruta] : []
  })

test.describe('Los iconos que se importan', () => {
  test('existen todos en el paquete', () => {
    const importados = new Map()
    for (const ruta of ficheros('src')) {
      const texto = readFileSync(ruta, 'utf8')
      for (const [, icono] of texto.matchAll(/@mui\/icons-material\/([A-Za-z0-9]+)/g)) {
        if (!importados.has(icono)) importados.set(icono, ruta)
      }
    }

    // El contraste, y aquí hace falta: si la extracción dejara de encontrar
    // importaciones, cero inexistentes se leería como «todos existen».
    expect(importados.size, 'no se ha encontrado ninguna importación de icono').toBeGreaterThan(15)

    const inventados = [...importados]
      .filter(([icono]) => {
        try {
          return !statSync(join(ICONOS, `${icono}.js`)).isFile()
        } catch {
          return true
        }
      })
      .map(([icono, ruta]) => `${icono} (${ruta})`)

    expect(
      inventados,
      'estos iconos no existen en @mui/icons-material. Vite devuelve un 500 al ' +
        'pedir el módulo y la pantalla se queda en blanco, sin decir por qué',
    ).toEqual([])
  })
})
