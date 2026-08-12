import axios from 'axios'

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

// Every API error has the same shape: { error: { code, message, details } }.
// It is normalised here so no component has to dig through the response.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const payload = error.response?.data?.error
    const status = error.response?.status ?? 0

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
const rows = (data) => (Array.isArray(data) ? data : (data?.results ?? []))

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

// ---------------------------------------------------------------- clock events

export const getToday = () => get('/punches/today/')
export const clock = (deviceId) => post('/punches/', { device_id: deviceId })
export const getPunches = async (params) => rows(await get('/punches/', params))
// No hay `voidPunch`: anular un fichaje se hace con una corrección de tipo
// VOID, que exige motivo, deja autor y avisa a la persona. Un atajo sin esas
// garantías vaciaría el procedimiento.

// ----------------------------------------------------------------- corrections

export const getCorrections = async (params) => rows(await get('/corrections/', params))
export const requestCorrection = (payload) => post('/corrections/', payload)
export const approveCorrection = (id, note = '') => post(`/corrections/${id}/approve/`, { note })
export const rejectCorrection = (id, note = '') => post(`/corrections/${id}/reject/`, { note })

// --------------------------------------------------------------------- absences

export const getAbsences = async (params) => rows(await get('/absences/', params))
export const getAbsenceCalendar = async (from, to) =>
  rows(await get('/absences/calendar/', { from, to }))
export const getPendingAbsences = async () => rows(await get('/absences/pending/'))
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

export const getEmployees = async (params) => rows(await get('/employees/', params))
export const getEmployee = (id) => get(`/employees/${id}/`)
export const createEmployee = (payload) => post('/employees/', payload)
export const updateEmployee = async (id, payload) =>
  (await api.patch(`/employees/${id}/`, payload)).data
export const deactivateEmployee = async (id) => (await api.delete(`/employees/${id}/`)).data

export const getDepartments = async (params) => rows(await get('/departments/', params))
export const createDepartment = (payload) => post('/departments/', payload)
export const updateDepartment = async (id, payload) =>
  (await api.patch(`/departments/${id}/`, payload)).data
export const deleteDepartment = async (id) => (await api.delete(`/departments/${id}/`)).data

// ---------------------------------------------------------------------- shifts

export const getShiftPatterns = async () => rows(await get('/shift-patterns/'))
export const createShiftPattern = (payload) => post('/shift-patterns/', payload)
export const updateShiftPattern = async (id, payload) =>
  (await api.patch(`/shift-patterns/${id}/`, payload)).data
export const deleteShiftPattern = async (id) => (await api.delete(`/shift-patterns/${id}/`)).data

export const getRoster = async (from, to) => rows(await get('/shifts/roster/', { from, to }))
export const assignShifts = (payload) => post('/shifts/assign/', payload)
export const clearShifts = (payload) => post('/shifts/clear/', payload)
export const reviewRoster = (from, to) => get('/shifts/review/', { from, to })
export const getMyShiftToday = () => get('/shifts/today/')

export const getWorkingTimeRules = () => get('/working-time-rules/')
export const updateWorkingTimeRules = async (payload) =>
  (await api.patch('/working-time-rules/', payload)).data

// ----------------------------------------------------------------------- audit

export const getAuditTrail = async (params) => rows(await get('/audit/', params))

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
