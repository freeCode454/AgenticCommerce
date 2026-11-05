import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUiStore = defineStore('ui', () => {
  const toasts = ref<{ id: number; message: string; tone: 'success' | 'error' | 'info' }[]>([])
  const confirmation = ref<{
    title: string
    message: string
    action: string
    danger?: boolean
  } | null>(null)
  let serial = 0
  let resolveConfirmation: ((value: boolean) => void) | undefined
  function dismiss(id: number) {
    toasts.value = toasts.value.filter((toast) => toast.id !== id)
  }
  function notify(message: string, tone: 'success' | 'error' | 'info' = 'success') {
    const id = ++serial
    toasts.value.push({ id, message, tone })
    if (toasts.value.length > 4) toasts.value.shift()
    setTimeout(() => dismiss(id), tone === 'error' ? 8000 : 4500)
  }
  function answer(value: boolean) {
    confirmation.value = null
    resolveConfirmation?.(value)
    resolveConfirmation = undefined
  }
  function confirm(
    title: string,
    message: string,
    action = '确认',
    danger = false,
  ): Promise<boolean> {
    if (confirmation.value) return Promise.resolve(false)
    confirmation.value = { title, message, action, danger }
    return new Promise((resolve) => {
      resolveConfirmation = resolve
    })
  }
  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text)
      notify('已复制到剪贴板')
    } catch {
      notify('复制失败，请选中文字后手动复制。', 'error')
    }
  }
  return { toasts, confirmation, notify, dismiss, confirm, answer, copy }
})
