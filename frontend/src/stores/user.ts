import { defineStore } from 'pinia'
import { ref } from 'vue'
import client from '@/api/client'

export const useUserStore = defineStore('user', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const userInfo = ref<any>(null)

  function setToken(newToken: string) {
    token.value = newToken
    localStorage.setItem('token', newToken)
  }

  function clearToken() {
    token.value = null
    userInfo.value = null
    localStorage.removeItem('token')
  }

  async function fetchUser() {
    const response = await client.get('/auth/me')
    userInfo.value = response.data.data
  }

  return { token, userInfo, setToken, clearToken, fetchUser }
})
