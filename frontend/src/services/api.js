import axios from 'axios'

const baseURL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api'

export const api = axios.create({
  baseURL,
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
})

// Todos los errores de la API traen la misma forma:
//   { error: { code, message, details } }
// Se normaliza aquí para que ningún componente tenga que escarbar en la respuesta.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const payload = error.response?.data?.error
    return Promise.reject({
      code: payload?.code ?? 'network_error',
      message: payload?.message ?? 'No se ha podido contactar con el servidor.',
      details: payload?.details ?? {},
      status: error.response?.status ?? 0,
    })
  },
)

export const getHealth = async () => {
  const { data } = await api.get('/health/')
  return data
}
