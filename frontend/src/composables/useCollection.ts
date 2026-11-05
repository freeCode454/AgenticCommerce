import { reactive, onMounted, onUnmounted, watch } from 'vue'
import axios from 'axios'
import client from '@/api/client'
import { errorMessage, statusCode } from '@/utils/format'
import type { ApiResponse, PageData } from '@/types'

interface Collection<T> {
  items: T[]
  total: number
  page: number
  size: number
  loading: boolean
  error: string
  errorCode: number
  hasMore: boolean
  params: Record<string, string | number | undefined>
  reload: (reset?: boolean) => Promise<void>
}
export function useCollection<T>(
  endpoint: string,
  size = 12,
  params: Collection<T>['params'] = {},
): Collection<T> {
  const state = reactive({
    items: [],
    total: 0,
    page: 1,
    size,
    loading: true,
    error: '',
    errorCode: 0,
    hasMore: false,
    params,
    reload: async () => {},
  }) as Collection<T>
  let controller: AbortController | undefined
  let sequence = 0
  let disposed = false
  async function load() {
    const request = ++sequence
    controller?.abort()
    controller = new AbortController()
    state.loading = true
    state.error = ''
    state.errorCode = 0
    try {
      const response = await client.get<ApiResponse<PageData<T>>>(endpoint, {
        params: { page: state.page, page_size: state.size, ...state.params },
        signal: controller.signal,
      })
      if (disposed || request !== sequence) return
      const data = response.data.data
      state.items = data.items || []
      state.total = data.total ?? data.count ?? state.items.length
      state.hasMore =
        data.total != null
          ? state.page * state.size < data.total
          : state.items.length === state.size
    } catch (error) {
      if (disposed || request !== sequence || axios.isCancel(error)) return
      state.error = errorMessage(error)
      state.errorCode = statusCode(error)
    } finally {
      if (!disposed && request === sequence) state.loading = false
    }
  }
  state.reload = async (reset = false) => {
    if (reset && state.page !== 1) state.page = 1
    else await load()
  }
  watch(
    () => state.page,
    () => {
      void load()
    },
  )
  onMounted(load)
  onUnmounted(() => {
    disposed = true
    ++sequence
    controller?.abort()
  })
  return state
}
