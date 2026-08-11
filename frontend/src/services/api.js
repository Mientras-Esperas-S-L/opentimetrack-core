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
  return config
})

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

export const getHealth = async () => (await api.get('/health/')).data

export const signIn = async (credentials) => {
  const { data } = await api.post('/auth/token/', credentials)
  tokens.save(data)
  return data
}

export const signUp = async (payload) => {
  const { data } = await api.post('/auth/register/', payload)
  tokens.save(data)
  return data
}

export const signOut = async () => {
  try {
    await api.post('/auth/logout/', { refresh: tokens.refresh })
  } finally {
    tokens.clear()
  }
}

export const getMe = async () => (await api.get('/auth/me/')).data
export const getToday = async () => (await api.get('/punches/today/')).data
export const clock = async (deviceId) => (await api.post('/punches/', { device_id: deviceId })).data
export const getPunches = async (params) => (await api.get('/punches/', { params })).data
