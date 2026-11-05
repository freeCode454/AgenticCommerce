import { defineStore } from 'pinia'
import { ref } from 'vue'
import client from '@/api/client'
import { errorMessage } from '@/utils/format'
import type { ApiResponse, UserInfo } from '@/types'
export const useUserStore = defineStore('user', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const userInfo = ref<UserInfo | null>(null)
  const identityError = ref('')
  let inFlight: Promise<UserInfo> | null = null
  function setToken(value: string) {
    token.value = value
    localStorage.setItem('token', value)
    userInfo.value = null
    identityError.value = ''
    inFlight = null
  }
  function clearToken() {
    token.value = null
    userInfo.value = null
    identityError.value = ''
    inFlight = null
    localStorage.removeItem('token')
  }
  async function fetchUser(): Promise<UserInfo> {
    if (inFlight) return inFlight
    const current = token.value
    const request = client
      .get<ApiResponse<UserInfo>>('/auth/me')
      .then((response) => {
        if (current !== token.value) throw new Error('Session changed')
        userInfo.value = response.data.data
        identityError.value = ''
        return response.data.data
      })
      .catch((error) => {
        if (current === token.value) identityError.value = errorMessage(error)
        throw error
      })
      .finally(() => {
        if (inFlight === request) inFlight = null
      })
    inFlight = request
    return request
  }
  window.addEventListener('auth-expired', clearToken)
  return { token, userInfo, identityError, setToken, clearToken, fetchUser }
})
