import { computed, onUnmounted, ref, watch, type Ref } from 'vue'
import { useRouter } from 'vue-router'
import client from '@/api/client'
import { useUserStore } from '@/stores/user'
import { errorMessage, statusCode } from '@/utils/format'
import type { ApiResponse, TaskDetail, NodeRun, PageData } from '@/types'

export function useTaskWorkspace(taskId: Ref<string>) {
  const detail = ref<TaskDetail | null>(null),
    nodes = ref<NodeRun[]>([]),
    loading = ref(true),
    refreshing = ref(false),
    error = ref(''),
    connection = ref('正在连接')
  const errorCode = ref(0)
  const router = useRouter(),
    user = useUserStore()
  const running = computed(() =>
    ['running', 'retrying', 'pending'].includes(detail.value?.task.status || ''),
  )
  let ws: WebSocket | null = null,
    heartbeat: ReturnType<typeof setInterval> | undefined,
    reconnect: ReturnType<typeof setTimeout> | undefined,
    scheduled: ReturnType<typeof setTimeout> | undefined,
    authenticationTimeout: ReturnType<typeof setTimeout> | undefined
  let controller: AbortController | undefined,
    sequence = 0,
    epoch = 0,
    disposed = false,
    attempts = 0
  const latest = computed(() => {
    const map: Record<string, NodeRun> = {}
    for (const node of nodes.value) map[node.node_name] = node
    return map
  })
  async function refresh() {
    if (!taskId.value || disposed) return
    const id = taskId.value,
      request = ++sequence
    controller?.abort()
    controller = new AbortController()
    refreshing.value = true
    try {
      const [task, node] = await Promise.all([
        client.get<ApiResponse<TaskDetail>>(`/tasks/${encodeURIComponent(id)}`, {
          signal: controller.signal,
        }),
        client.get<ApiResponse<PageData<NodeRun>>>(`/tasks/${encodeURIComponent(id)}/nodes`, {
          signal: controller.signal,
        }),
      ])
      if (disposed || request !== sequence) return
      detail.value = task.data.data
      nodes.value = node.data.data.items
      error.value = ''
    } catch (cause) {
      if (!disposed && request === sequence) {
        error.value = errorMessage(cause, '任务详情暂不可用，请重试。')
        errorCode.value = statusCode(cause)
      }
    } finally {
      if (!disposed && request === sequence) {
        refreshing.value = false
        loading.value = false
      }
    }
  }
  function clearSocket() {
    clearInterval(heartbeat)
    clearTimeout(reconnect)
    clearTimeout(scheduled)
    clearTimeout(authenticationTimeout)
    if (ws) {
      ws.onopen = null
      ws.onmessage = null
      ws.onclose = null
      ws.onerror = null
      ws.close()
      ws = null
    }
  }
  function scheduleRefresh() {
    clearTimeout(scheduled)
    scheduled = setTimeout(() => void refresh(), 150)
  }
  function connect() {
    if (disposed || !taskId.value || !user.token) return
    const ownEpoch = epoch
    connection.value = attempts ? '正在重新连接' : '正在连接'
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const socket = new WebSocket(
      `${protocol}//${location.host}/api/v1/ws/tasks/${encodeURIComponent(taskId.value)}`,
    )
    ws = socket
    authenticationTimeout = setTimeout(() => {
      if (socket.readyState !== WebSocket.CLOSED && connection.value !== '实时连接正常')
        socket.close(4000, 'Authentication timeout')
    }, 10000)
    socket.onopen = () => {
      if (ownEpoch === epoch)
        socket.send(JSON.stringify({ type: 'authenticate', token: user.token }))
    }
    socket.onmessage = (event) => {
      if (disposed || ownEpoch !== epoch) return
      if (event.data === 'pong') return
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'authenticated') {
          clearTimeout(authenticationTimeout)
          connection.value = '实时连接正常'
          clearInterval(heartbeat)
          heartbeat = setInterval(() => {
            if (socket.readyState === WebSocket.OPEN) socket.send('ping')
          }, 25000)
          scheduleRefresh()
        } else if (['node_update', 'task_update'].includes(data.type)) scheduleRefresh()
      } catch {
        connection.value = '消息暂不可用，将定时刷新'
      }
    }
    socket.onerror = () => {
      if (ownEpoch === epoch) connection.value = '连接中断，将定时刷新'
    }
    socket.onclose = (event) => {
      if (disposed || ownEpoch !== epoch) return
      clearTimeout(authenticationTimeout)
      clearInterval(heartbeat)
      connection.value = '连接中断，将定时刷新'
      if (event.code === 4401) {
        user.clearToken()
        void router.replace({
          path: '/login',
          query: { redirect: `/workbench/${taskId.value}` },
        })
        return
      }
      if ([4403, 4404].includes(event.code)) {
        connection.value = '实时订阅不可用，将定时刷新'
        return
      }
      const waits = [1000, 2000, 4000, 8000, 15000]
      if (attempts < waits.length) {
        const delay = waits[attempts++]
        reconnect = setTimeout(connect, delay)
      } else connection.value = '重连已暂停，正在定时刷新'
    }
  }
  function reconnectNow() {
    clearSocket()
    attempts = 0
    connect()
  }
  watch(
    taskId,
    () => {
      ++epoch
      clearSocket()
      controller?.abort()
      ++sequence
      detail.value = null
      nodes.value = []
      error.value = ''
      loading.value = true
      attempts = 0
      void refresh()
      connect()
    },
    { immediate: true },
  )
  const poll = setInterval(() => {
    if (running.value && connection.value !== '实时连接正常' && !refreshing.value) void refresh()
  }, 5000)
  onUnmounted(() => {
    disposed = true
    ++epoch
    ++sequence
    controller?.abort()
    clearSocket()
    clearInterval(poll)
  })
  return {
    detail,
    nodes,
    latest,
    loading,
    refreshing,
    error,
    errorCode,
    connection,
    running,
    refresh,
    reconnectNow,
  }
}
