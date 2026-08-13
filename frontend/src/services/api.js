import axios from 'axios'

import { noteServerTime } from './serverClock.js'

const baseURL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api'

const ACCESS = 'ott.access'
const REFRESH = 'ott.refresh'

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
    renewing = api
      .post('/auth/refresh/', { refresh: tokens.refresh })
      .then(({ data }) => {
        tokens.save(data)
        return data.access
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
        } catch {
          tokens.clear()
        }
      }
    }

    if (status === 401) tokens.clear()

    return Promise.reject({
      code: payload?.code ?? 'network_error',
      message: payload?.message ?? 'The server could not be reached.',
      details: payload?.details ?? {},
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
export const clock = (deviceId) => post('/punches/', { device_id: deviceId })
export const getPunches = async (params) => page(await get('/punches/', params))
// No hay `voidPunch`: anular un fichaje se hace con una corrección de tipo
// VOID, que exige motivo, deja autor y avisa a la persona. Un atajo sin esas
// garantías vaciaría el procedimiento.

// ----------------------------------------------------------------- corrections

export const getCorrections = async (params) => page(await get('/corrections/', params))
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

// ------------------------------------------------- avisos en el navegador

/** La clave pública del despliegue, y si el push está configurado siquiera.
 *  Sin claves no se ofrece: proponer un aviso que no va a llegar es peor que
 *  no proponerlo. */
export const getPushKey = () => get('/push/key/')
export const subscribePush = (payload) => post('/push/subscriptions/', payload)
export const unsubscribePush = (endpoint) =>
  api.delete('/push/subscriptions/', { data: { endpoint } })
export const getLeaveBalance = (employee) => get('/absences/balance/', employee ? { employee } : {})
export const requestAbsence = (payload) => post('/absences/', payload)
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

export const getDepartments = async (params) => rows(await get('/departments/', params))
export const createDepartment = (payload) => post('/departments/', payload)
export const updateDepartment = async (id, payload) =>
  (await api.patch(`/departments/${id}/`, payload)).data
export const deleteDepartment = async (id) => (await api.delete(`/departments/${id}/`)).data

/** Centros de trabajo. Cualquiera los lee: una persona tiene derecho a saber
 *  dónde se lleva su registro y qué calendario de festivos se le aplica. */
export const getWorkplaces = async (params) => rows(await get('/workplaces/', params))
export const createWorkplace = (payload) => post('/workplaces/', payload)
export const updateWorkplace = async (id, payload) =>
  (await api.patch(`/workplaces/${id}/`, payload)).data
export const deleteWorkplace = async (id) => (await api.delete(`/workplaces/${id}/`)).data

/** Festivos. Cualquiera los lee: son los días que no se espera que trabaje, y
 *  de ellos depende su saldo de vacaciones. */
export const getHolidays = async (params) => rows(await get('/holidays/', params))
export const createHoliday = (payload) => post('/holidays/', payload)
export const deleteHoliday = async (id) => (await api.delete(`/holidays/${id}/`)).data

/** El catálogo de permisos de la empresa. Cualquiera lo lee: nadie puede pedir
 *  un permiso que no ve, y lo que necesita saber antes de pedirlo es cuánto da
 *  y de qué artículo sale. */
export const getLeaveTypes = async (params) =>
  rows(await get('/leave-types/', { is_active: true, ...params }))
export const createLeaveType = (payload) => post('/leave-types/', payload)
export const updateLeaveType = async (id, payload) =>
  (await api.patch(`/leave-types/${id}/`, payload)).data
export const seedLeaveTypes = () => post('/leave-types/seed/', {})

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

export const getShiftPatterns = async () => rows(await get('/shift-patterns/'))
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
