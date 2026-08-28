/** La interfaz en catalán y gallego, no solo el servidor.
 *
 *  El mecanismo estaba montado desde antes ---i18next, con **la cadena castellana
 *  como clave**, así que lo que falta cae al castellano igual que en el backend---
 *  y lo usaban dos pantallas de treinta y ocho: el catálogo tenía 23 claves y eran
 *  las del menú. Una empresa catalana veía el menú en catalán y las pantallas en
 *  castellano.
 *
 *  Esta prueba recorre lo traducido en cada idioma. Crece con el catálogo: al
 *  envolver una pantalla nueva se añade aquí su texto más característico, y con
 *  eso la traducción deja de poder desaparecer sin que nadie se entere.
 *
 *  Se elige texto **de la propia pantalla**, no del menú: el menú ya estaba
 *  traducido y comprobarlo daría verde sin haber traducido nada más.
 */

import { expect, test } from '@playwright/test'

import { api, irA } from './apoyo.js'

/** Qué se espera ver en cada idioma, por pantalla. */
const PANTALLAS = [
  {
    ruta: '/panel/personas',
    titulo: { es: 'Personas', ca: 'Persones', gl: 'Persoas' },
    // Un texto largo de la propia pantalla, que no sale en ningún menú.
    propio: {
      es: 'Dar de baja no borra nada',
      ca: 'Donar de baixa no esborra res',
      gl: 'Dar de baixa non borra nada',
    },
    // Y un rótulo de control, que es la otra mitad de lo que se traduce.
    control: {
      es: 'Ver también las bajas',
      ca: 'Veure també les baixes',
      gl: 'Ver tamén as baixas',
    },
  },
  {
    ruta: '/panel/ajustes',
    titulo: {
      es: 'Ajustes de la empresa',
      ca: "Configuració de l'empresa",
      gl: 'Axustes da empresa',
    },
    propio: {
      es: 'identifica a la empresa en cada informe',
      ca: "identifica l'empresa a cada informe",
      gl: 'identifica a empresa en cada informe',
    },
    control: {
      es: 'Registro de jornada (años)',
      ca: 'Registre de jornada (anys)',
      gl: 'Rexistro de xornada (anos)',
    },
    // `type="number"` de MUI expone rol `spinbutton`, no `textbox`.
    rol: 'spinbutton',
  },
  {
    ruta: '/mi-jornada',
    titulo: { es: 'Mi jornada', ca: 'La meva jornada', gl: 'A miña xornada' },
    propio: {
      es: 'Tienes derecho a consultarlo',
      ca: 'Tens dret a consultar-lo',
      gl: 'Tes dereito a consultalo',
    },
    control: {
      es: 'Pedir una corrección',
      ca: 'Demanar una correcció',
      gl: 'Pedir unha corrección',
    },
    rol: 'button',
  },
  {
    ruta: '/panel/centros',
    titulo: {
      es: 'Centros de trabajo',
      ca: 'Centres de treball',
      gl: 'Centros de traballo',
    },
    propio: {
      es: 'Decide los festivos locales',
      ca: 'Decideix els festius locals',
      gl: 'Decide os festivos locais',
    },
    control: { es: 'Nuevo centro', ca: 'Nou centre', gl: 'Novo centro' },
    rol: 'button',
  },
  {
    ruta: '/panel/fichajes',
    titulo: { es: 'Fichajes', ca: 'Fitxatges', gl: 'Fichaxes' },
    propio: {
      es: 'Un fichaje anulado sigue siendo legible',
      ca: 'Un fitxatge anul·lat continua sent llegible',
      gl: 'Unha fichaxe anulada segue sendo lexible',
    },
    control: { es: 'Hasta', ca: 'Fins a', gl: 'Ata' },
    rol: 'textbox',
  },
  {
    // El título no sirve de muestra aquí: «Por decidir» se escribe igual en
    // castellano y en gallego. La muestra es el subtítulo, que sí cambia.
    ruta: '/panel/decisiones',
    titulo: { es: 'Por decidir', ca: 'Per decidir', gl: 'Por decidir' },
    propio: {
      es: 'Toda decisión queda registrada con su autor',
      ca: 'Tota decisió queda registrada amb el seu autor',
      gl: 'Toda decisión queda rexistrada co seu autor',
    },
    control: { es: 'Sin acuerdo', ca: 'Sense acord', gl: 'Sen acordo' },
    rol: 'tab',
  },
  {
    ruta: '/panel/cuadrante',
    titulo: { es: 'Cuadrante', ca: 'Quadrant', gl: 'Cadro de quendas' },
    propio: {
      es: 'lo fichado se guarda aparte',
      ca: 'el que es fitxa es desa a part',
      gl: 'o fichado gárdase á parte',
    },
    control: { es: 'Asignar turno', ca: 'Assignar un torn', gl: 'Asignar unha quenda' },
    rol: 'button',
  },
  {
    ruta: '/panel/permisos',
    titulo: { es: 'Permisos', ca: 'Permisos', gl: 'Permisos' },
    propio: {
      es: 'La ley es el suelo',
      ca: 'La llei és el sòl',
      gl: 'A lei é o piso',
    },
    control: {
      es: 'Buscar por nombre o artículo',
      ca: 'Cerca per nom o article',
      gl: 'Buscar por nome ou artigo',
    },
    rol: 'textbox',
  },
  {
    ruta: '/panel/aplicaciones',
    titulo: { es: 'Aplicaciones', ca: 'Aplicacions', gl: 'Aplicacións' },
    propio: {
      es: 'revocable sin tocar la cuenta de nadie',
      ca: 'revocable sense tocar el compte de ningú',
      gl: 'revogable sen tocar a conta de ninguén',
    },
  },
  {
    ruta: '/panel/informes',
    titulo: { es: 'Informes', ca: 'Informes', gl: 'Informes' },
    propio: {
      es: 'El documento que se entrega a la Inspección',
      ca: 'El document que es lliura a la Inspecció',
      gl: 'O documento que se entrega á Inspección',
    },
    control: {
      es: 'Descargar PDF',
      ca: 'Descarregar el PDF',
      gl: 'Descargar o PDF',
    },
    rol: 'button',
  },
  {
    ruta: '/panel/calendario',
    titulo: {
      es: 'Calendario del equipo',
      ca: "Calendari de l'equip",
      gl: 'Calendario do equipo',
    },
    propio: {
      es: 'Las solicitudes sin resolver aparecen rayadas',
      ca: 'Les sol·licituds sense resoldre surten ratllades',
      gl: 'As solicitudes sen resolver aparecen raiadas',
    },
    control: { es: 'Volver a hoy', ca: 'Tornar a avui', gl: 'Volver a hoxe' },
    rol: 'button',
  },
  {
    ruta: '/panel/departamentos',
    titulo: { es: 'Departamentos', ca: 'Departaments', gl: 'Departamentos' },
    propio: {
      es: 'Una persona puede no tener ninguno',
      ca: 'Una persona pot no tenir-ne cap',
      gl: 'Unha persoa pode non ter ningún',
    },
    control: { es: 'Nuevo', ca: 'Nou', gl: 'Novo' },
    rol: 'button',
  },
  {
    // La pantalla de fichar, que es la que más gente ve y la única que ve
    // quien no gestiona nada.
    ruta: '/',
    titulo: { es: 'Hola,', ca: 'Hola,', gl: 'Ola,' },
    propio: {
      es: 'trabajadas hoy',
      ca: 'treballades avui',
      gl: 'traballadas hoxe',
    },
    control: { es: 'Fichar entrada', ca: "Fitxar l'entrada", gl: 'Fichar a entrada' },
    rol: 'button',
  },
]

test.describe('La pantalla, en los tres idiomas', () => {
  test.use({ storageState: 'e2e/.sesiones/admin.json' })

  test('las muestras elegidas sirven para comprobar algo', () => {
    /** Se cayó en esto al ampliar la tabla: «Mes anterior» se escribe igual en
     *  castellano, catalán y gallego, así que la comprobación de que el texto
     *  castellano **ya no está** no podía cumplirse nunca.
     *
     *  Una muestra que no cambia entre idiomas no distingue «traducido» de «sin
     *  traducir». Esto lo dice en un rojo claro en vez de en uno confuso a
     *  cuatro pantallas de distancia.
     */
    for (const { ruta, propio, control } of PANTALLAS) {
      for (const idioma of ['ca', 'gl']) {
        expect(propio[idioma], `${ruta}: el texto de muestra es igual en es y ${idioma}`).not.toBe(
          propio.es,
        )
        // `control` es opcional: hay pantallas cuyos rótulos de control se
        // escriben igual en los tres idiomas ---«Autorizar»--- y forzar uno
        // sería inventarse una traducción para que la prueba tenga qué mirar.
        if (control) {
          expect(control[idioma], `${ruta}: el control es igual en es y ${idioma}`).not.toBe(
            control.es,
          )
        }
      }
    }
  })

  for (const idioma of ['ca', 'gl', 'es']) {
    test(`en ${idioma}`, async ({ page }) => {
      // Se pide desde la sesión, que es de donde lo saca `ConIdioma`, y se
      // devuelve al final: dejar el idioma cambiado rompería las demás pruebas
      // en un sitio donde nadie miraría.
      // Hay que estar en la aplicación antes de usar `api`: lee el testigo de
      // `localStorage`, y en `about:blank` el navegador ni deja mirarlo.
      await page.goto('/')
      const antes = (await api(page, '/auth/me/')).body?.locale ?? ''
      try {
        const puesto = await api(page, '/auth/me/', {
          method: 'PATCH',
          body: { locale: idioma === 'es' ? '' : idioma },
        })
        expect(puesto.status, 'no se pudo cambiar el idioma').toBe(200)

        for (const { ruta, titulo, propio, control, rol = 'switch' } of PANTALLAS) {
          await irA(page, ruta, titulo[idioma])
          await expect(page.getByText(new RegExp(propio[idioma], 'i')).first()).toBeVisible()
          if (control) {
            await expect(page.getByRole(rol, { name: control[idioma] }).first()).toBeVisible()
          }

          // Y que de verdad ha cambiado: en catalán o gallego, el texto
          // castellano no puede seguir en pantalla. Sin esto la prueba pasaría
          // con el catálogo vacío, porque la clave **es** el castellano.
          if (idioma !== 'es') {
            await expect(page.getByText(propio.es, { exact: false })).toHaveCount(0)
            if (control) {
              await expect(page.getByRole(rol, { name: control.es })).toHaveCount(0)
            }
          }
        }
      } finally {
        await api(page, '/auth/me/', { method: 'PATCH', body: { locale: antes } })
      }
    })
  }

  /** Lo que sale en todas las pantallas a la vez.
   *
   *  `components/common.jsx` ---el paginador, los estados, el aviso de plazo
   *  agotado--- y `filters.jsx` no son de ninguna pantalla y están en todas.
   *  Comprobarlos por la tabla de arriba no distingue si lo que se tradujo fue
   *  la pantalla o el trozo compartido: esto los mira aparte.
   */
  test('lo que comparten todas las pantallas', async ({ page }) => {
    await page.goto('/')
    const antes = (await api(page, '/auth/me/')).body?.locale ?? ''
    try {
      await api(page, '/auth/me/', { method: 'PATCH', body: { locale: 'ca' } })
      await irA(page, '/panel/fichajes', 'Fitxatges')

      // El «todos» de un desplegable de filtro, que lo pone `filters.jsx` y
      // no la pantalla. No sirve el texto del buscador: todas las pantallas le
      // pasan el suyo, así que el de por defecto no se lee en ninguna.
      await expect(page.getByRole('combobox', { name: 'Origen' })).toBeVisible()
      await page.getByRole('combobox', { name: 'Origen' }).click()
      await expect(page.getByRole('option', { name: 'Tots', exact: true })).toBeVisible()
      await expect(page.getByRole('option', { name: 'Todos', exact: true })).toHaveCount(0)
      await page.keyboard.press('Escape')
      await expect(page.getByRole('listbox')).toHaveCount(0)

      // Y el contador del paginador, con su sustantivo: la frase la arma
      // `Pager` y el sustantivo lo pone quien lo usa, así que si falla
      // cualquiera de los dos lados esto se ve.
      await expect(page.getByText(/\d+ fitxatges/).first()).toBeVisible()
      await expect(page.getByText(/\d+ fichajes/)).toHaveCount(0)
    } finally {
      await api(page, '/auth/me/', { method: 'PATCH', body: { locale: antes } })
    }
  })

  /** El formulario de pedir una ausencia.
   *
   *  No es una pantalla y por eso no está en la tabla: hay que abrirlo. Y es el
   *  fichero con más texto de todo el frontend ---cincuenta y cinco cadenas---,
   *  con el saldo, los avisos de tope y las condiciones del convenio, así que
   *  vale por varias pantallas de las de arriba.
   */
  test('el formulario de pedir una ausencia, entero', async ({ page }) => {
    await page.goto('/')
    const antes = (await api(page, '/auth/me/')).body?.locale ?? ''
    try {
      await api(page, '/auth/me/', { method: 'PATCH', body: { locale: 'ca' } })
      await irA(page, '/mis-ausencias', /Mis ausencias|Les meves absències/)

      // El botón que lo abre es de la pantalla, no del diálogo, y esa pantalla
      // todavía no está traducida. Vale cualquiera de los dos rótulos para que
      // esto no se ponga rojo el día que le toque su tanda.
      await page.getByRole('button', { name: /^(Solicitar|Demanar)$/ }).click()

      const dialogo = page.getByRole('dialog')
      await expect(dialogo.getByText('Demanar una absència')).toBeVisible()
      await expect(dialogo.getByLabel('Què demanes')).toBeVisible()
      await expect(dialogo.getByText('Solicitar ausencia')).toHaveCount(0)
      await expect(dialogo.getByLabel('Qué pides')).toHaveCount(0)

      await page.keyboard.press('Escape')
      await expect(page.getByRole('dialog')).toHaveCount(0)
    } finally {
      await api(page, '/auth/me/', { method: 'PATCH', body: { locale: antes } })
    }
  })

  /** Las fechas.
   *
   *  Se escribían con `'es-ES'` fijo en nueve sitios, así que una pantalla
   *  traducida entera seguía diciendo «agosto de 2026». Lo que no cambia se ve
   *  más que lo que falta: parece un descuido, no un trabajo a medias.
   *
   *  El gallego no sirve de muestra aquí ---escribe los meses igual que el
   *  castellano---, así que la comprobación es en catalán.
   */
  test('las fechas también hablan el idioma', async ({ page }) => {
    // «Abril» y «octubre» se escriben igual en castellano y en catalán, así que
    // dos meses al año esta prueba no distinguiría nada ---y escrita del revés,
    // se pondría roja sola sin que nada estuviera mal---. Si toca uno de esos,
    // avanza al siguiente, que sí difiere.
    const AMBIGUOS = /abril|octubre/i
    const EN_CATALAN = /gener|febrer|març|maig|juny|juliol|agost|setembre|novembre|desembre/i
    const EN_CASTELLANO =
      /enero|febrero|marzo|mayo|junio|julio|agosto|septiembre|noviembre|diciembre/i

    await page.goto('/')
    const antes = (await api(page, '/auth/me/')).body?.locale ?? ''
    try {
      await api(page, '/auth/me/', { method: 'PATCH', body: { locale: 'ca' } })
      await irA(page, '/panel/cuadrante', 'Quadrant')

      const leer = async () => (await page.locator('main').innerText()).replace(/\s+/g, ' ')
      if (AMBIGUOS.test(await leer())) {
        await page.getByRole('button', { name: 'Mes següent' }).click()
        await expect.poll(async () => AMBIGUOS.test(await leer())).toBe(false)
      }

      const cabecera = await leer()
      expect(cabecera, 'el mes no sale en catalán').toMatch(EN_CATALAN)
      expect(cabecera, 'el mes sigue en castellano').not.toMatch(EN_CASTELLANO)
    } finally {
      await api(page, '/auth/me/', { method: 'PATCH', body: { locale: antes } })
    }
  })
})
