import axios from 'axios'
const client = axios.create({ baseURL: '/api/v1', timeout: 30000 })
let redirecting = false
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      window.dispatchEvent(new Event('auth-expired'))
      if (window.location.pathname !== '/login' && !redirecting) {
        redirecting = true
        const redirect = window.location.pathname + window.location.search + window.location.hash
        window.location.assign(`/login?redirect=${encodeURIComponent(redirect)}`)
      }
    }
    return Promise.reject(error)
  },
)
export default client
