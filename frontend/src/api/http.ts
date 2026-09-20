import axios, { type AxiosError } from 'axios'
import { ElMessage } from 'element-plus'

const TOKEN_KEY = 'ops_token'
const USER_KEY = 'ops_username'
const MUST_CHANGE_KEY = 'ops_must_change'

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function setAuthSession(token: string, username: string, mustChange: boolean): void {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, username)
  localStorage.setItem(MUST_CHANGE_KEY, mustChange ? '1' : '0')
}

export function setMustChangePassword(flag: boolean): void {
  localStorage.setItem(MUST_CHANGE_KEY, flag ? '1' : '0')
}

export function getMustChangePassword(): boolean {
  return localStorage.getItem(MUST_CHANGE_KEY) === '1'
}

export function getUsername(): string {
  return localStorage.getItem(USER_KEY) || ''
}

export function clearAuthSession(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
  localStorage.removeItem(MUST_CHANGE_KEY)
}

function extractError(err: unknown): string {
  const ax = err as AxiosError<{ detail?: string; message?: string }>
  const detail = ax?.response?.data?.detail || ax?.response?.data?.message
  if (typeof detail === 'string' && detail) return detail
  if (Array.isArray(detail) && detail.length) {
    return detail.map((d) => (typeof d === 'string' ? d : JSON.stringify(d))).join('; ')
  }
  if (ax?.message) return ax.message
  return '请求失败'
}

export const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api/v1',
  timeout: 30000,
})

http.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

http.interceptors.response.use(
  (resp) => resp,
  (error: AxiosError) => {
    const status = error.response?.status
    const message = extractError(error)
    if (status === 401) {
      clearAuthSession()
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = '/login'
      }
    }
    if (status === 403 && /password change required/i.test(message)) {
      setMustChangePassword(true)
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = '/login?force_change=1'
      }
    }
    ElMessage.error(message)
    return Promise.reject(error)
  },
)

export function isProjectDeployEnabled(): boolean {
  return import.meta.env.VITE_PROJECT_DEPLOY_ENABLED === 'true'
}

export function buildWsLogsUrl(nodeId: string): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const base = import.meta.env.VITE_API_BASE || '/api/v1'
  const token = getToken()
  const qs = token ? `?token=${encodeURIComponent(token)}` : ''
  return `${proto}//${window.location.host}${base}/nodes/${encodeURIComponent(nodeId)}/logs${qs}`
}
