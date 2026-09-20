import { http } from './http'
import type { ChangePasswordPayload, HealthResp, LoginPayload, LoginResult } from './types'

export function loginApi(payload: LoginPayload) {
  return http.post<LoginResult>('/auth/login', payload)
}

export function changePasswordApi(payload: ChangePasswordPayload) {
  return http.post<{ ok: boolean }>('/auth/change-password', payload)
}

export function healthApi() {
  return http.get<HealthResp>('/health')
}
