/** La tanda no puede dejar residuos en la empresa de demostración.
 *
 *  **Por qué existe.** Cuatro vueltas seguidas se fueron en arreglar pruebas que
 *  fallaban por lo que había dejado otra, y cada vez el síntoma señalaba un
 *  sitio distinto del culpable:
 *
 *  - dos cuentas apellidadas «Bloque» del 14 de agosto se colaban al principio
 *    del orden alfabético y una prueba movía a quien no era;
 *  - una ausencia sin resolver en unas fechas fijas chocaba con la de la tanda
 *    anterior;
 *  - **ocho centros** de prueba acumulados ponían tres botones «Editar» en una
 *    pantalla y tumbaban la comprobación de nombres accesibles;
 *  - un ajuste de empresa que no se restauró dejó el tope de jornada en 26 y
 *    rompió las pruebas de Ajustes de las corridas siguientes.
 *
 *  Arreglar el caso de turno no converge: el sedimento vuelve por donde no se
 *  mira. Esto lo convierte en un fallo **inmediato y con nombre**, en la tanda
 *  que lo produce y no tres vueltas después.
 *
 *  Corre el último porque el fichero empieza por `zz`, que es como Playwright
 *  ordena los ficheros. Y no limpia nada a propósito: si limpiara, la prueba
 *  descuidada seguiría estándolo y nadie se enteraría.
 */

import { expect, test } from '@playwright/test'

import { api, irA } from './apoyo.js'

/** Lo que crean las pruebas: la marca de `apoyo.js` o un prefijo conocido.
 *
 *  La marca lleva **doce caracteres o más** tras la `p` ---el instante en base 36
 *  y cuatro al azar--- o siete dígitos si es de las viejas. El primer intento
 *  pedía solo seis y señalaba a `parcial@demo.local`, que es de la semilla: un
 *  guard que grita por lo que tiene que estar ahí se apaga a la semana.
 */
const DE_PRUEBA =
  /(^|[ .-])(p[0-9a-z]{12,}|p\d{7,})|^(prueba|bloque|masiva|idioma|colado|repe|cobertura|extremos)\b/i

/** Sujetos fijos que algunas pruebas reutilizan a propósito.
 *
 *  No son sedimento: son **el mismo** de una tanda a la siguiente. Su correo
 *  está escrito en la prueba, así que por muchas veces que se corra sigue
 *  habiendo uno. Lo que este guard persigue es lo que **crece**, no lo que
 *  existe.
 *
 *  Y quedan activos por una razón dicha en su sitio: la prueba de cobertura
 *  da de baja a esta persona como parte del caso, y si no le devolviera el alta
 *  saldría como hueco de plantilla en todas las tandas siguientes.
 *
 *  La lista es cerrada a posta. Añadir un correo aquí es declarar que ese
 *  sujeto se reutiliza; si una prueba necesita uno nuevo cada vez, lo que toca
 *  es que lo retire, no ampliar esta lista.
 */
const REUTILIZADOS = [
  'cobertura.prueba@example.com',
  'extremos.prueba@example.com',
  // Los dos de `14-decidir-en-bloque`. Esa prueba **aprueba** ausencias, y una
  // aprobada no se cancela, así que quien la tiene ya no se puede borrar. Antes
  // creaba gente nueva cada pasada para estrenar calendario y dejaba dos
  // irrecuperables por tanda; ahora reutiliza estos dos y se mueve de fechas.
  'bloque.uno@demo.local',
  'bloque.dos@demo.local',
]

/** Qué hacer cuando esto falla, dicho en el propio fallo. */
const COMO_SE_ARREGLA =
  'La prueba que lo creó tiene que retirarlo en un `finally`; para personas ya ' +
  'existe `darDeBajaLasDePrueba(page, sufijo)` en `apoyo.js`.'

/** La lista entera, no la primera página.
 *
 *  Con veintiuna personas activas todo cabe de una vez y pedir la página por
 *  defecto habría bastado ---por eso pasó en verde a la primera---. Pero el
 *  sedimento crece: en cuanto pasara de veinte, el guard estaría mirando las
 *  veinte primeras y callándose sobre el resto, ciego justo cuando hace falta.
 *
 *  **Recorre las páginas**, y no se conforma con pedir `page_size=1000`: el
 *  servidor tiene su propio tope y devuelve lo que quiere, no lo que se le
 *  pide. Pedir mil y comprobar que no hay una segunda página se ponía rojo a
 *  las cincuenta y una bajas ---por debajo del tope de sesenta que este guard
 *  dice vigilar---, así que el guard no podía llegar a medir su propio límite.
 *  Un tope que no se alcanza nunca no es un tope: es un rojo que llega antes.
 */
async function listaEntera(page, ruta, filtro = '') {
  const filas = []
  for (let pagina = 1; pagina <= PAGINAS_COMO_MUCHO; pagina += 1) {
    const { body } = await api(page, `${ruta}?page_size=1000&page=${pagina}${filtro}`)
    filas.push(...(body?.results ?? (Array.isArray(body) ? body : [])))
    if (!body?.next) return filas
  }
  // Y si se agotan las páginas, se dice: callarlo sería exactamente lo que este
  // recorrido existe para evitar.
  throw new Error(
    `${ruta} tiene más de ${PAGINAS_COMO_MUCHO} páginas. Esta comprobación estaría ` +
      'mirando una parte y dando por limpio lo que no ha visto.',
  )
}

/** Un tope al recorrido, no a la lista: si algo devolviera `next` para siempre,
 *  la suite se quedaría dando vueltas en vez de fallar. */
const PAGINAS_COMO_MUCHO = 40

test.use({ storageState: 'e2e/.sesiones/admin.json' })

test.describe('Al terminar la tanda', () => {
  /** El sedimento de las de baja, que no es cero pero no puede crecer sin techo.
   *
   *  La comprobación de al lado mira solo las activas, y su razón está escrita:
   *  «el producto no borra personas a propósito, que los fichajes viven cuatro
   *  años». Es verdad a medias. **Lo era del todo para quien tiene fichajes**, y
   *  falso para quien no tiene ninguno: el 27/08 había **946 personas de prueba
   *  dadas de baja en la empresa de demostración, ninguna con un solo fichaje**,
   *  de 969 personas en total. La pantalla de Personas era basura en un 98 %.
   *
   *  Y el razonamiento se muerde la cola: no se miraban porque eran demasiadas
   *  para traerlas en una página, y eran demasiadas porque nadie las miraba.
   *
   *  Esto no exige cero, porque la API **no borra personas** ---y hace bien, con
   *  los fichajes viviendo cuatro años---, así que una prueba que da de alta a
   *  alguien y lo retira solo puede dejarlo de baja. Lo que hace es avisar cuando
   *  el sedimento pasa de un tope. El tope es un cortafuegos, no un objetivo: si
   *  salta, la salida no es subirlo.
   */
  const TOPE_DE_BAJA = 60

  test('el sedimento de personas de prueba dadas de baja no crece sin techo', async ({ page }) => {
    await irA(page, '/panel/personas', 'Personas')

    const deBaja = await listaEntera(page, '/employees/', '&is_active=false')
    const sedimento = deBaja
      .filter((p) => !REUTILIZADOS.includes(p.email))
      .filter((p) => DE_PRUEBA.test(p.email ?? '') || DE_PRUEBA.test(p.full_name ?? ''))

    expect(
      sedimento.length,
      `hay ${sedimento.length} personas de prueba dadas de baja y el tope está en ` +
        `${TOPE_DE_BAJA}. No se arregla subiendo el tope: o una prueba está creando ` +
        'personas que no necesita, o hace falta poder borrar de verdad a quien no ' +
        'tiene ni un fichaje ---un alta equivocada no puede quedarse para siempre---. ' +
        `${COMO_SE_ARREGLA}`,
    ).toBeLessThanOrEqual(TOPE_DE_BAJA)
  })

  test('no quedan personas de prueba dadas de alta', async ({ page }) => {
    await irA(page, '/panel/personas', 'Personas')

    // Filtrado en el servidor: las de baja son cientos ---la API tope el
    // `page_size`, así que traerlas todas partiría la lista en páginas--- y no
    // estorban a nadie. Lo que se busca son las que siguen activas.
    const activas = await listaEntera(page, '/employees/', '&is_active=true')

    const sobran = activas
      .filter((p) => !REUTILIZADOS.includes(p.email))
      .filter((p) => DE_PRUEBA.test(p.email ?? '') || DE_PRUEBA.test(p.full_name ?? ''))
      .map((p) => p.email)

    expect(
      sobran,
      'una prueba dio de alta a alguien y no lo retiró. Las de baja no estorban ' +
        '---el producto no borra personas a propósito, que los fichajes viven ' +
        `cuatro años--- pero una activa se cuela en los listados y en las ` +
        `selecciones de las demás pruebas. ${COMO_SE_ARREGLA}`,
    ).toEqual([])

    // Y los reutilizados tienen que seguir siendo uno cada uno. Si una prueba
    // deja de encontrar el suyo ---por un filtro que cambia, por una búsqueda
    // que falla--- da de alta otro con el mismo correo y la lista empieza a
    // crecer por donde nadie mira, que es justo lo que esto viene a evitar.
    const repetidos = REUTILIZADOS.filter(
      (correo) => activas.filter((p) => p.email === correo).length > 1,
    )
    expect(
      repetidos,
      'un sujeto de los que se reutilizan está duplicado: la prueba que lo usa ' +
        'no lo encontró y dio de alta otro',
    ).toEqual([])
  })

  test('no quedan centros de trabajo de prueba', async ({ page }) => {
    await irA(page, '/panel/centros', 'Centros de trabajo')

    const sobran = (await listaEntera(page, '/workplaces/'))
      .filter((c) => DE_PRUEBA.test(c.name ?? ''))
      .map((c) => c.name)

    expect(
      sobran,
      'una prueba creó un centro y no lo retiró. Con tres, la pantalla tiene tres ' +
        `botones «Editar» y la comprobación de nombres accesibles falla en otro ` +
        `sitio. ${COMO_SE_ARREGLA}`,
    ).toEqual([])
  })

  test('no quedan departamentos de usar y tirar', async ({ page }) => {
    await irA(page, '/panel/departamentos', 'Departamentos')

    const sobran = (await listaEntera(page, '/departments/'))
      .filter((d) => DE_PRUEBA.test(d.name ?? ''))
      .map((d) => d.name)

    expect(sobran, `una prueba creó un departamento y no lo retiró. ${COMO_SE_ARREGLA}`).toEqual([])
  })

  test('no quedan festivos inventados', async ({ page }) => {
    await irA(page, '/panel/centros', 'Centros de trabajo')

    // Por año, que es como los pide la pantalla: el de ahora y sus dos vecinos,
    // que son los únicos que el selector ofrece y por tanto los únicos donde una
    // prueba puede haber dejado algo.
    const ahora = new Date().getFullYear()
    const sobran = []
    for (const año of [ahora - 1, ahora, ahora + 1]) {
      const dias = await listaEntera(page, '/holidays/', `&year=${año}`)
      sobran.push(
        ...dias.filter((d) => DE_PRUEBA.test(d.name ?? '')).map((d) => `${d.day} ${d.name}`),
      )
    }

    expect(
      sobran,
      'una prueba inventó festivos y no los retiró. Un día marcado como festivo ' +
        `cambia lo que se espera que la gente trabaje. ${COMO_SE_ARREGLA}`,
    ).toEqual([])
  })

  test('los ajustes de la empresa quedan como estaban', async ({ page }) => {
    await irA(page, '/panel/ajustes', 'Ajustes de la empresa')

    const reglas = (await api(page, '/working-time-rules/')).body

    // Los de la semilla. Una prueba que los cambia tiene que devolverlos en un
    // `finally` --- y comprobando la respuesta, porque desde que cambiar el
    // cómputo exige fecha de efecto una restauración mal hecha falla en silencio.
    expect(
      { tope: reglas.max_open_hours, pausa: reglas.break_counts_as_work },
      'una prueba cambió cómo se cuenta el tiempo y no lo devolvió a como estaba',
    ).toEqual({ tope: 16, pausa: false })
  })
})
