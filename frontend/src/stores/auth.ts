import { computed, ref, watch } from 'vue'
import { changePasswordApi, loginApi } from '@/api/auth'
import {
  clearAuthSession,
  getMustChangePassword,
  getToken,
  getUsername,
  setAuthSession,
  setMustChangePassword,
} from '@/api/http'

const token = ref(getToken())
const username = ref(getUsername())
const mustChangePassword = ref(getMustChangePassword())

export function useAuthStore() {
  const isLoggedIn = computed(() => !!token.value)

  async function login(user: string, password: string) {
    const { data } = await loginApi({ username: user, password })
    token.value = data.access_token
    username.value = user
    mustChangePassword.value = !!data.must_change_password
    setAuthSession(data.access_token, user, data.must_change_password)
    return data
  }

  async function changePassword(oldPassword: string, newPassword: string) {
    await changePasswordApi({ old_password: oldPassword, new_password: newPassword })
    mustChangePassword.value = false
    setMustChangePassword(false)
  }

  function logout() {
    token.value = ''
    username.value = ''
    mustChangePassword.value = false
    clearAuthSession()
  }

  return {
    token,
    username,
    mustChangePassword,
    isLoggedIn,
    login,
    changePassword,
    logout,
  }
}

watch(token, (val) => {
  if (!val) {
    username.value = ''
  }
})
