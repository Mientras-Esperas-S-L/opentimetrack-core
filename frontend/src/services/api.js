import axios from 'axios'

import { noteServerTime } from './serverClock.js'

const baseURL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api'

const ACCESS = 'ott.access'
const REFRESH = 'ott.refresh'

/** A quién avisar cuando la sesión se pierde de verdad.
 *
 *  Hacía falta porque `tokens.clear()` vacía el almacén y **nadie se entera**.
 *  Con la aplicación abierta y el acceso caducado, una consulta de fondo
 *  recibía 401, el testigo se borraba... y la pantalla seguía puesta: React no
 *  sabía nada. La consulta del panel se repite cada minuto, así que el
 *  resultado era un 401 por minuto para siempre, con la persona delante de una
 *  pantalla que no se arreglaba sola ni la mandaba a entrar.
 *
 *  Salió en la consola de un uso real el 13/08/2026, no en las pruebas: las
 *  que había navegaban, y al navegar se vuelve a comprobar la sesión y todo
 *  funciona. El caso roto es quedarse quieto dentro.
 */
let alPerderLaSesion = null

export const onSessionLost = (fn) => {
  alPerderLaSesion = fn
}

export const tokens = {
  get access() {
    return localStorage.getItem(ACCESS)
  },
  get refresh() {
    return localStorage.getItem(REFRESH)
  },
  save({ access, refresh }) {
    localStorage.setItem(ACCESS, access)
    localStorage.setItem(REFRESH, refresh)
  },
  clear() {
    localStorage.removeItem(ACCESS)
    localStorage.removeItem(REFRESH)
  },
}

export const api = axios.create({
  baseURL,
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = tokens.access
  if (token) config.headers.Authorization = `Bearer ${token}`

  // Labels that reach the screen --- absence types, clock-event origins, error
  // messages --- are translated server-side, and Django picks the language from
  // this header. Without it the API answers in English regardless of the
  // interface, which is how "Holiday" ended up next to "Vacaciones".
  config.headers['Accept-Language'] = preferredLanguage
  return config
})

/** Language for API responses.
 *
 *  Order: the person's own setting, then their company's, then the browser.
 *  The browser is the weakest of the three because it says where somebody is
 *  sitting, not what language their employer works in --- and a phone set to
 *  English does not mean the worker wants their payslip terms in English.
 */
let preferredLanguage = navigator.language || 'es'

export const setPreferredLanguage = (session) => {
  preferredLanguage =
    session?.user?.locale || session?.tenant?.language || navigator.language || 'es'
}

/** Renovar la sesión sin que se note, y una sola vez por petición.
 *
 *  El acceso dura quince minutos y el refresco siete días. Hasta el 13/08/2026
 *  el segundo se guardaba y no se usaba nunca --- no había ni endpoint --- así
 *  que la sesión se moría a media jornada, a media pantalla, y devolvía a la
 *  gente al login habiendo perdido lo que estaba haciendo.
 *
 *  Una promesa compartida: si cinco peticiones caducan a la vez, se refresca
 *  una vez y las cinco esperan a la misma. Refrescar cinco veces con rotación
 *  activada invalidaría los tokens de las otras cuatro.
 */
let renewing = null

const renew = () => {
  if (!renewing) {
    // El que había al empezar. Hace falta guardarlo para poder distinguir
    // después «mi refresco ya no vale» de «otra pestaña lo cambió».
    const usado = tokens.refresh
    renewing = api
      .post('/auth/refresh/', { refresh: usado })
      .then(({ data }) => {
        tokens.save(data)
        return data.access
      })
      .catch((fallo) => {
        // La promesa compartida de arriba evita que cinco peticiones de **esta**
        // pestaña refresquen cinco veces. Entre pestañas no sirve: cada una
        // tiene su propio módulo y su propio `renewing`, y las dos leen el mismo
        // refresco de `localStorage`.
        //
        // Con la rotación activada eso es una carrera con perdedor: la primera
        // rota el refresco y manda el viejo a la lista negra, y a la segunda le
        // contestan que su sesión caducó ---cuando lo que ha pasado es que su
        // compañera acaba de renovarla. Tener dos pestañas abiertas echaba de
        // una de ellas cada vez que caducaba el acceso.
        //
        // El canal para enterarse ya existe y es el mismo `localStorage`: si lo
        // que hay ahí ahora no es lo que se envió, alguien lo cambió mientras
        // esta petición estaba en vuelo. Un solo reintento, con el nuevo.
        const ahora = tokens.refresh
        if (ahora && ahora !== usado) {
          return api.post('/auth/refresh/', { refresh: ahora }).then(({ data }) => {
            tokens.save(data)
            return data.access
          })
        }
        throw fallo
      })
      .finally(() => {
        renewing = null
      })
  }
  return renewing
}

// Every API error has the same shape: { error: { code, message, details } }.
// It is normalised here so no component has to dig through the response.
api.interceptors.response.use(
  (response) => {
    // Toda respuesta trae su hora. De ahí sale el reloj de pared de la pantalla
    // de fichar, para que no sea el del dispositivo.
    noteServerTime(response.headers?.date)
    return response
  },
  async (error) => {
    noteServerTime(error.response?.headers?.date)
    const payload = error.response?.data?.error
    const status = error.response?.status ?? 0
    const failed = error.config

    // Un 401 con refresco a mano es una sesión que se renueva, no una que se
    // acabó. `_retried` evita el bucle: si la repetición también da 401, se
    // cierra de verdad.
    if (status === 401 && tokens.refresh && failed && !failed._retried) {
      const renewingThis = failed.url?.includes('/auth/refresh/')
      if (!renewingThis) {
        failed._retried = true
        try {
          const access = await renew()
          failed.headers.Authorization = `Bearer ${access}`
          return api(failed)
        } catch (fallo) {
          // **Solo si el servidor dice que la sesión no vale.** Un 502 del
          // balanceador mientras se despliega, un 429 de la cubeta que comparte
          // toda una oficina detrás del mismo NAT, o el wifi parpadeando, no
          // dicen nada sobre el refresco --- y el refresco dura siete días.
          //
          // Tratarlos como sesión caducada tiraba a la calle a quien llevaba
          // cinco minutos rellenando un alta, le borraba el formulario y
          // destruía además un testigo que seguía siendo bueno: recargar ya no
          // la devolvía dentro, tenía que volver a teclear la contraseña.
          //
          // Es la misma distinción que `AuthContext` hace para `/auth/me/`, con
          // el mismo motivo escrito allí. Aquí faltaba.
          //
          // `session_expired` entra en la lista porque **este servidor no
          // contesta 401 a un refresco malo**: lo trata como regla de negocio y
          // sale con 409. Mirar solo el estado dejaba fuera el caso legítimo ---
          // el refresco caducado de verdad--- y entonces nadie volvía al
          // formulario de entrada. Se comprueba por código, que es explícito,
          // y no por el 409, que significa muchas otras cosas.
          const rechazo =
            fallo?.status === 401 || fallo?.status === 403 || fallo?.code === 'session_expired'
          if (!rechazo) {
            throw fallo
          }
          tokens.clear()
        }
      }
    }

    if (status === 401) {
      // Definitivo: o no había refresco, o el refresco lo rechazó de verdad, o
      // la repetición con el testigo nuevo volvió a dar 401.
      tokens.clear()
      alPerderLaSesion?.()
    }

    // El titular de un error de validación es siempre el mismo --- «Los datos
    // enviados no son válidos» --- y lo que de verdad pasa viaja en `details`.
    // Cuando el motivo no es de un campo concreto, DRF lo mete en
    // `non_field_errors`, y ese es el mensaje que hay que enseñar: la pantalla
    // de entrada decía «Los datos enviados no son válidos» donde el servidor
    // había dicho «Credenciales incorrectas».
    //
    // Aquí y no en cada pantalla, porque el que lo pintaba mal era cada una.
    const { non_field_errors: general, ...porCampo } = payload?.details ?? {}
    const concreto = Array.isArray(general) ? general[0] : general

    // `network_error` y un plazo agotado no son lo mismo, y la diferencia
    // decide qué se le puede decir a quien acaba de fichar. Sin respuesta y sin
    // haber salido, no ha quedado nada. Sin respuesta **después** de que la
    // petición viajara, el servidor ha podido registrarla perfectamente: es el
    // modo de fallo normal de una obra con mala cobertura, y afirmar ahí que no
    // se registró nada es lo que provoca el segundo fichaje.
    const plazoAgotado =
      !error.response && (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT')

    return Promise.reject({
      code: payload?.code ?? (plazoAgotado ? 'timeout' : 'network_error'),
      // En castellano, como el resto del producto. Estaba en inglés, y es el
      // único texto que lee quien está en una obra y no consigue fichar: el
      // peor sitio posible para el idioma equivocado.
      message:
        concreto ||
        payload?.message ||
        (plazoAgotado ? 'El servidor tarda en contestar.' : 'No hay conexión con el servidor.'),
      details: porCampo,
      status,
    })
  },
)

const get = async (path, params) => (await api.get(path, { params })).data
const post = async (path, body, config) => (await api.post(path, body, config)).data

// A list endpoint is paginated; a plain array comes back from the custom
// actions. Callers should not have to know which, so it is flattened here.
//
// Only for endpoints that answer with everything. Using it on a paginated one
// throws away `count` and `next` --- which is exactly what used to happen, and
// meant the clock events, the people and the audit trail all showed the first
// fifty rows and said nothing about the rest. Fifty punches is about a day and
// a half; "el registro tal y como está guardado" was a slice.
const rows = (data) => (Array.isArray(data) ? data : (data?.results ?? []))

/** A page of a paginated list, keeping how many there are and whether more
 *  follow. `count` is what lets a screen say "1-50 de 1.284" instead of
 *  implying the list is complete. */
const page = (data) => ({
  rows: rows(data),
  count: Array.isArray(data) ? data.length : (data?.count ?? 0),
  hasMore: Boolean(data?.next),
})

/** How many rows a page holds. Mirrors DRF's PAGE_SIZE: the client cannot ask
 *  the server what it is, and guessing wrong would misnumber every page. */
export const PAGE_SIZE = 50

/** Un periodo acotado, entero: recorre las páginas hasta traerlo todo.
 *
 * Un `Pager` no sirve para todas las listas. Los fichajes de una persona se
 * pintan agrupados por jornada, así que cortar cada cincuenta filas dejaría la
 * entrada de un día en una página y su salida en la siguiente: no es que se vea
 * incómodo, es que el día se lee mal. Y son los fichajes de esa persona, que el
 * art. 34.9 le da derecho a consultar.
 *
 * El tope existe para no encadenar peticiones sin final si el filtro se va de
 * las manos. Cuando se alcanza, la respuesta lo dice con `hasMore` en vez de
 * hacer pasar por completo lo que no lo está: quien la usa tiene que avisar.
 */
const periodoEntero = async (path, params, { tope = 20 } = {}) => {
  const filas = []
  let ultima = { count: 0, hasMore: false }
  for (let numero = 1; numero <= tope; numero += 1) {
    ultima = page(await get(path, { ...params, page: numero }))
    filas.push(...ultima.rows)
    if (!ultima.hasMore) return { rows: filas, count: ultima.count, hasMore: false }
  }
  return { rows: filas, count: ultima.count, hasMore: true }
}

/** Un catálogo entero, que es como el producto lo necesita.
 *
 *  `rows()` se queda con la primera página y tira `next` sin decir nada. Para
 *  una lista con `Pager` da igual ---la pantalla ya dice «1-50 de 1.284»---,
 *  pero un catálogo alimenta un **selector**, y lo que no se carga no se puede
 *  elegir: nadie ve un error, sencillamente la opción no está.
 *
 *  Ninguna vista del backend desactiva la paginación, así que estos cinco
 *  venían cortados a cincuenta desde siempre. Hoy el catálogo de permisos va
 *  por treinta y dos, y los festivos de un año pasan de cincuenta en cuanto la
 *  empresa tiene centros en varios municipios --- dos locales por cada uno.
 *
 *  Si de verdad hubiera más de mil, `periodoEntero` deja de pedir y aquí se
 *  dice: callarlo sería el mismo fallo con otro número.
 */
const catalogoEntero = async (path, params) => {
  const { rows: filas, count, hasMore } = await periodoEntero(path, params)
  if (hasMore) {
    console.warn(
      `[catálogo] ${path} tiene ${count} elementos y se han traído ${filas.length}: ` +
        'lo que falta no se podrá elegir',
    )
  }
  return filas
}

export const getHealth = () => get('/health/')

// ------------------------------------------------------------------- session

export const signIn = async (credentials) => {
  const data = await post('/auth/token/', credentials)
  tokens.save(data)
  return data
}

export const signUp = async (payload) => {
  const data = await post('/auth/register/', payload)
  tokens.save(data)
  return data
}

export const signOut = async () => {
  try {
    await post('/auth/logout/', { refresh: tokens.refresh })
  } finally {
    tokens.clear()
  }
}

export const getMe = () => get('/auth/me/')

/** Cambiar las preferencias propias (idioma, recordatorios). Solo eso: el
 *  servidor ignora todo lo demás. */
export const updateMe = async (payload) => (await api.patch('/auth/me/', payload)).data

/** Asks for a link to set a password. Always resolves, whether the address
 *  exists or not: telling the two apart would turn this into a way of finding
 *  out who works where, so the screen says the same thing either way. */
export const requestPasswordReset = (email) => post('/auth/password-reset/', { email })

/** Sets the password from the link and signs in with it, so nobody has to type
 *  the password they have just chosen. */
export const setPasswordFromLink = async (payload) => {
  const data = await post('/auth/set-password/', payload)
  tokens.save(data)
  return data
}

// ---------------------------------------------------------------- clock events

export const getToday = () => get('/punches/today/')
/** Ficha. El servidor decide si es entrada o salida, y de qué.
 *
 *  `interval` dice **qué** se abre o se cierra: la jornada (art. 3.c) o una
 *  pausa que no es tiempo de trabajo (art. 3.d). El tipo se deduce del estado
 *  de ese intervalo, así que el mismo botón abre y cierra la pausa sin que el
 *  cliente tenga que llevar la cuenta.
 *
 *  `workMode` es el art. 3.e ---presencial o a distancia, para el día o parte
 *  de él---. Se manda solo si la persona lo ha dicho: vacío es «no consta», y
 *  eso es más honesto que suponer «presencial» y llenar el registro de un dato
 *  que nadie ha afirmado. */
export const clock = (deviceId, { interval, workMode } = {}) =>
  post('/punches/', {
    device_id: deviceId,
    ...(interval ? { interval } : {}),
    ...(workMode ? { work_mode: workMode } : {}),
  })
export const getPunches = async (params) => page(await get('/punches/', params))
/** Todos los fichajes del periodo, sin partir ninguna jornada. */
export const getAllPunches = (params) => periodoEntero('/punches/', params)
// No hay `voidPunch`: anular un fichaje se hace con una corrección de tipo
// VOID, que exige motivo, deja autor y avisa a la persona. Un atajo sin esas
// garantías vaciaría el procedimiento.

// ----------------------------------------------------------------- corrections

export const getCorrections = async (params) => page(await get('/corrections/', params))
/** Todas las solicitudes de una persona: son suyas y las mira de una vez. */
export const getAllCorrections = (params) => periodoEntero('/corrections/', params)
export const requestCorrection = (payload) => post('/corrections/', payload)
export const approveCorrection = (id, note = '') => post(`/corrections/${id}/approve/`, { note })
export const rejectCorrection = (id, note = '') => post(`/corrections/${id}/reject/`, { note })

// Art. 4.b: cambiar un asiento necesita la autorización de las dos partes, y
// sin acuerdo la empresa lo aplica dejando constancia de la discrepancia. Las
// tres llamadas existían en el backend desde el ADR-0014 y no había pantalla
// que las usara: una corrección propuesta por la empresa pasaba a esperar
// respuesta y se quedaba ahí para siempre.
export const acceptCorrection = (id) => post(`/corrections/${id}/accept/`)
export const disputeCorrection = (id, account) => post(`/corrections/${id}/dispute/`, { account })
export const applyCorrectionAnyway = (id) => post(`/corrections/${id}/apply-anyway/`)

// --------------------------------------------------------------------- absences

export const getAbsences = async (params) => page(await get('/absences/', params))
export const getAbsenceCalendar = async (from, to) =>
  rows(await get('/absences/calendar/', { from, to }))
export const getPendingAbsences = async () => rows(await get('/absences/pending/'))

/** Horas extra pendientes de que un responsable las autorice o rechace. */
export const getPendingOvertime = async () => (await get('/overtime/')).pending ?? []
export const decideOvertime = (payload) => post('/overtime/', payload)

/** Días de vacaciones que una baja se comió y esperan confirmación (art. 38.3). */
export const getHolidayRecoveries = async () => (await get('/holiday-recoveries/')).pending ?? []
export const confirmHolidayRecovery = (payload) => post('/holiday-recoveries/', payload)

// ------------------------------------------------- avisos en el navegador

/** La clave pública del despliegue, y si el push está configurado siquiera.
 *  Sin claves no se ofrece: proponer un aviso que no va a llegar es peor que
 *  no proponerlo. */
export const getPushKey = () => get('/push/key/')
export const subscribePush = (payload) => post('/push/subscriptions/', payload)
export const unsubscribePush = (endpoint) =>
  api.delete('/push/subscriptions/', { data: { endpoint } })
export const getLeaveBalance = (employee) => get('/absences/balance/', employee ? { employee } : {})
/** Pedir una ausencia, con su justificante si lo lleva.
 *
 *  El fichero obliga a `multipart`, así que se arma un FormData solo cuando lo
 *  hay: mandar todo como multipart siempre convertiría cada `null` en la cadena
 *  «null» al otro lado, que es de los errores que tardan un día en verse.
 */
export const requestAbsence = (payload) => {
  if (!payload?.justification) return post('/absences/', payload)

  const cuerpo = new FormData()
  for (const [campo, valor] of Object.entries(payload)) {
    if (valor === undefined || valor === null || valor === '') continue
    cuerpo.append(campo, valor)
  }
  return post('/absences/', cuerpo, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: plazoParaSubir(payload.justification?.size),
  })
}

/** Cuánto esperar por una subida, según lo que pesa.
 *
 *  Los diez segundos de siempre valen para una petición que solo lleva texto y
 *  no para una foto de ocho megas: la pantalla anuncia «PDF o foto, hasta 10
 *  MB», y ese límite solo se cumplía si la subida iba a más de 8 Mb/s
 *  sostenidos. Por debajo, axios abortaba **con el cuerpo ya enviado**: el
 *  servidor creaba la solicitud y a la persona se le decía que no había
 *  conexión. Se iba creyendo que no había pedido el permiso mientras su
 *  responsable lo veía en la cola.
 *
 *  128 KB/s es una subida de 4G mala, no una buena: el plazo tiene que aguantar
 *  el peor caso razonable, porque agotarlo de menos falsea lo que se le cuenta a
 *  quien está esperando. Diez megas salen a poco más de minuto y medio.
 */
const SUBIDA_BYTES_POR_SEGUNDO = 128 * 1024

export const plazoParaSubir = (bytes) => {
  const peso = Number(bytes) || 0
  return 10_000 + Math.ceil(peso / SUBIDA_BYTES_POR_SEGUNDO) * 1000
}
export const approveAbsence = (id) => post(`/absences/${id}/approve/`)
export const rejectAbsence = (id) => post(`/absences/${id}/reject/`)
export const cancelAbsence = (id) => post(`/absences/${id}/cancel/`)

/** Downloads a supporting document.
 *
 *  There is no URL to link to on purpose: the server checks who is asking
 *  before handing anything over, and with object storage it redirects to a
 *  signed URL that expires. A path in the JSON would be a bearer secret sitting
 *  in every list response.
 */
export const downloadJustification = async (id, filename = 'justificante') => {
  const response = await api.get(`/absences/${id}/justification/`, { responseType: 'blob' })
  const url = URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

// ---------------------------------------------------------------------- people

export const getEmployees = async (params) => page(await get('/employees/', params))
export const getEmployee = (id) => get(`/employees/${id}/`)
export const createEmployee = (payload) => post('/employees/', payload)
export const updateEmployee = async (id, payload) =>
  (await api.patch(`/employees/${id}/`, payload)).data
export const deactivateEmployee = async (id) => (await api.delete(`/employees/${id}/`)).data
export const reactivateEmployee = async (id) =>
  (await api.patch(`/employees/${id}/`, { is_active: true })).data
export const inviteEmployee = (id) => post(`/employees/${id}/invite/`)

/** Manda a esa persona un enlace para descargar su propio registro.
 *
 *  Existe sobre todo para quien ya no trabaja aquí: su registro se conserva
 *  cuatro años (art. 34.9) y sigue teniendo derecho a pedirlo (art. 15 RGPD),
 *  pero no debería seguir entrando al producto. El enlace no abre sesión. */
export const deliverRecord = (id) => post(`/employees/${id}/deliver-record/`)

/** Borra de verdad a quien no dejó rastro.
 *
 *  Distinto de dar de baja, que es lo que hace `DELETE` y hace bien: los
 *  fichajes de quien trabajó aquí viven cuatro años y su ficha tiene que seguir
 *  explicándolos. Esto es para el alta equivocada ---el correo mal escrito, la
 *  persona duplicada--- que hasta ahora solo se podía desactivar y se quedaba en
 *  la lista para siempre.
 *
 *  El servidor se niega y dice qué encontró si hay algo que explicar. */
export const erasePerson = (id) => post(`/employees/${id}/erase/`)

export const getDepartments = async (params) => catalogoEntero('/departments/', params)
export const createDepartment = (payload) => post('/departments/', payload)
export const updateDepartment = async (id, payload) =>
  (await api.patch(`/departments/${id}/`, payload)).data
export const deleteDepartment = async (id) => (await api.delete(`/departments/${id}/`)).data

/** Centros de trabajo. Cualquiera los lee: una persona tiene derecho a saber
 *  dónde se lleva su registro y qué calendario de festivos se le aplica. */
export const getWorkplaces = async (params) => catalogoEntero('/workplaces/', params)
export const createWorkplace = (payload) => post('/workplaces/', payload)
export const updateWorkplace = async (id, payload) =>
  (await api.patch(`/workplaces/${id}/`, payload)).data
export const deleteWorkplace = async (id) => (await api.delete(`/workplaces/${id}/`)).data

/** Festivos. Cualquiera los lee: son los días que no se espera que trabaje, y
 *  de ellos depende su saldo de vacaciones. */
export const getHolidays = async (params) => catalogoEntero('/holidays/', params)
export const createHoliday = (payload) => post('/holidays/', payload)
export const deleteHoliday = async (id) => (await api.delete(`/holidays/${id}/`)).data

/** El catálogo de permisos de la empresa. Cualquiera lo lee: nadie puede pedir
 *  un permiso que no ve, y lo que necesita saber antes de pedirlo es cuánto da
 *  y de qué artículo sale. */
export const getLeaveTypes = async (params) =>
  catalogoEntero('/leave-types/', { is_active: true, ...params })
export const createLeaveType = (payload) => post('/leave-types/', payload)
export const updateLeaveType = async (id, payload) =>
  (await api.patch(`/leave-types/${id}/`, payload)).data
export const seedLeaveTypes = () => post('/leave-types/seed/', {})

/** Cómo se organizó el registro de jornada (art. 34.9, párrafo segundo).
 *
 *  Lo lee cualquiera de la empresa y lo escribe quien administra: el mismo
 *  párrafo pone el registro a disposición de las personas trabajadoras y de sus
 *  representantes, y saber con qué amparo se organizó es lo que permite a la
 *  representación comprobar que se la consultó.
 */
export const getRecordArrangement = () => get('/company/record-arrangement/')
export const updateRecordArrangement = async (payload) =>
  (await api.patch('/company/record-arrangement/', payload)).data

/** Lo que queda de cada permiso con tope. El catálogo dice que el art. 37.9 da
 *  cuatro días al año; esto dice que van dos. */
/** Lo que cada permiso lleva consumido. Es lo que pinta el aviso de «llevas X
 *  de Y» al pedir una ausencia.
 *
 *  `rows()` y no `.data`: el ayudante `get` ya devuelve el cuerpo, así que
 *  `.data` era `undefined` y la consulta reventaba en silencio --- el aviso de
 *  tope consumido no se ha enseñado nunca. Mismo fallo que tenía la cola de
 *  horas extra; si vuelve a aparecer, es que este ayudante engaña. */
export const getLeaveUsage = async (params) => rows(await get('/leave-types/usage/', params))

// ---------------------------------------------------------------------- shifts

export const getShiftPatterns = async () => catalogoEntero('/shift-patterns/')
export const createShiftPattern = (payload) => post('/shift-patterns/', payload)
export const updateShiftPattern = async (id, payload) =>
  (await api.patch(`/shift-patterns/${id}/`, payload)).data
export const deleteShiftPattern = async (id) => (await api.delete(`/shift-patterns/${id}/`)).data

export const getRoster = async (from, to) => rows(await get('/shifts/roster/', { from, to }))
export const assignShifts = (payload) => post('/shifts/assign/', payload)
export const clearShifts = (payload) => post('/shifts/clear/', payload)
/** A stroke drawn on the roster grid: cells, each with its own answer.
 *
 *  Separate from `assignShifts`, which takes a pattern and a rectangle. This
 *  takes a list of squares, which is what a drag produces and --- more to the
 *  point --- what undo needs, since a stroke can cross four different shifts
 *  and two blanks and has to put every one of them back.
 */
export const paintShifts = (cells) => post('/shifts/paint/', { cells })
export const reviewRoster = (from, to) => get('/shifts/review/', { from, to })

/** Los turnos que se han quedado sin nadie, con quién puede cogerlos.
 *
 *  Aparte de `reviewRoster` aunque el backend sepa las dos cosas: la revisión
 *  contesta «qué se aparta de la norma» y esto contesta «qué hay que resolver
 *  hoy». Mezclarlas dejaría los huecos enterrados entre veintidós clases de
 *  aviso, que es de donde venimos.
 */
export const getCoverage = (from, to) => get('/shifts/coverage/', { from, to })

/** Pasa un turno de una persona a otra. Una operación, no dos.
 *
 *  Asignar a la nueva y limpiar a la anterior por separado tiene un fallo en
 *  medio que deja el turno duplicado, o borrado y sin nadie.
 */
export const reassignShift = (id, employee) => post(`/shifts/${id}/reassign/`, { employee })
export const getMyShiftToday = () => get('/shifts/today/')

export const getWorkingTimeRules = () => get('/working-time-rules/')
export const updateWorkingTimeRules = async (payload) =>
  (await api.patch('/working-time-rules/', payload)).data

// ----------------------------------------------------------------------- audit

export const getAuditTrail = async (params) => page(await get('/audit/', params))

/** El resumen que acompaña a la nómina (art. 6.1). El periodo lo fija el ciclo
 *  de pago de la empresa, no quien pregunta: el artículo lo ata al «periodo
 *  fijado para el abono», y dejar elegir fechas produciría resúmenes que no
 *  cuadran con ninguna nómina. */
export const getPayrollSummary = (params) => get('/reports/payroll-summary/', params)

/** El mismo resumen, como documento. Devuelve el blob y el nombre que eligió el
 *  servidor, igual que `downloadReport`. */
export const downloadPayrollSummary = async (params) => {
  const response = await api.get('/reports/payroll-summary/', { params, responseType: 'blob' })
  const disposition = response.headers['content-disposition'] ?? ''
  const match = disposition.match(/filename="?([^"]+)"?/)
  return {
    blob: response.data,
    filename: match?.[1] ?? `resumen.${params?.format ?? 'pdf'}`,
  }
}
export const generatePayrollSummaries = (day) =>
  post('/reports/payroll-summary/', day ? { day } : {})

// --------------------------------------------------------------- applications

// Terminales, lectores y sistemas que fichan en nombre de alguien. Los modelos
// y el endpoint de fichaje delegado existían desde el principio y no había
// ninguna ruta para crear una aplicación: solo por shell de Django.
export const getApplications = async (params) => page(await get('/applications/', params))
export const getApplicationScopes = () => get('/applications/scopes/')
export const authoriseApplication = (payload) => post('/applications/', payload)
export const revokeApplication = async (id) => (await api.delete(`/applications/${id}/`)).data
/** Devuelve el token en claro. Es la única vez que existe fuera de quien lo
 *  guarde: se almacena cifrado y no se puede recuperar. */
export const issueCredential = (id, payload = {}) =>
  post(`/applications/${id}/credentials/`, payload)
export const revokeCredential = async (id, credential) =>
  (await api.post(`/applications/${id}/credentials/${credential}/revoke/`)).data

/** The trail as a file, with whatever filters are on screen. Not paginated on
 *  purpose: a page of fifty handed over as "the history" is the failure this
 *  screen already had once. */
export const downloadAuditTrail = async (params) => {
  const response = await api.get('/audit/export/', { params, responseType: 'blob' })
  saveBlob(response, 'actividad.csv')
}

/** Saves a downloaded blob under the name the server gave it. */
const saveBlob = (response, fallback) => {
  const disposition = response.headers['content-disposition'] ?? ''
  const named = /filename="?([^"]+)"?/.exec(disposition)
  const url = URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = url
  link.download = named ? named[1] : fallback
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

// -------------------------------------------------------------------- company

export const getCompany = () => get('/company/')
export const updateCompany = async (payload) => (await api.patch('/company/', payload)).data

// -------------------------------------------------------------------- overview

export const getOverview = () => get('/overview/')

// --------------------------------------------------------------------- reports

/** The report is always a file --- PDF or CSV --- never JSON, so there is only
 *  this one call. `format` is a query parameter, not an Accept header: the view
 *  declares renderers for both so DRF treats it as content negotiation.
 *
 *  Returns the blob and the filename the server chose, plus the fingerprint it
 *  puts in a header so a consumer can check the document without opening it.
 */
export const downloadReport = async (params) => {
  const response = await api.get('/reports/working-time/', { params, responseType: 'blob' })

  const disposition = response.headers['content-disposition'] ?? ''
  const match = disposition.match(/filename="?([^"]+)"?/)

  return {
    blob: response.data,
    filename: match?.[1] ?? `informe.${params.format ?? 'pdf'}`,
    fingerprint: response.headers['x-report-hash'] ?? '',
  }
}
