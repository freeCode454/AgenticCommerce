import { onMounted, onUnmounted, ref, shallowRef } from 'vue'
import axios from 'axios'
import client from '@/api/client'
import { errorMessage, statusCode } from '@/utils/format'
import type { ApiResponse } from '@/types'

export function useResource<T>(endpoint: string, auto = true) {
  const data = shallowRef<T | null>(null),
    loading = ref(auto),
    error = ref(''),
    errorCode = ref(0)
  let controller: AbortController | undefined,
    sequence = 0,
    disposed = false
  async function reload() {
    const seq = ++sequence
    controller?.abort()
    controller = new AbortController()
    loading.value = true
    error.value = ''
    errorCode.value = 0
    try {
      const result = await client.get<ApiResponse<T>>(endpoint, {
        signal: controller.signal,
      })
      if (!disposed && seq === sequence) data.value = result.data.data
    } catch (e) {
      if (!disposed && seq === sequence && !axios.isCancel(e)) {
        error.value = errorMessage(e)
        errorCode.value = statusCode(e)
      }
    } finally {
      if (!disposed && seq === sequence) loading.value = false
    }
  }
  onMounted(() => {
    if (auto) void reload()
  })
  onUnmounted(() => {
    disposed = true
    ++sequence
    controller?.abort()
  })
  return { data, loading, error, errorCode, reload }
}
