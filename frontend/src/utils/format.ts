import axios from 'axios'

export function errorMessage(error: unknown, fallback = '请求未完成，请稍后重试'): string {
  if (axios.isAxiosError(error)) {
    if (error.response?.status === 403) return '你没有访问此功能的权限，请联系管理员。'
    if (error.response?.status === 401) return '登录已失效，请重新登录。'
    const data = error.response?.data
    if (typeof data?.detail === 'string') return data.detail
    if (typeof data?.message === 'string') return data.message
    if (!error.response) return '暂时无法连接服务，请检查网络后重试。'
  }
  return fallback
}
export const statusCode = (error: unknown) =>
  axios.isAxiosError(error) ? (error.response?.status ?? 0) : 0
export const dateText = (value?: string) => {
  if (!value || Number.isNaN(new Date(value).getTime())) return '—'
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value))
}
export const numberText = (value?: number) =>
  typeof value === 'number' ? new Intl.NumberFormat('zh-CN').format(value) : '暂不可用'
export const moneyText = (value?: number) =>
  typeof value === 'number' ? `$${value.toFixed(4)}` : '暂不可用'
export const platformText = (value?: string) =>
  ({
    amazon: 'Amazon',
    shopify: 'Shopify',
    tiktok: 'TikTok Shop',
    tiktok_shop: 'TikTok Shop',
    temu: 'Temu',
  })[value || ''] ||
  value ||
  '—'
export function safeUrl(value?: string): string {
  if (!value) return ''
  try {
    const url = new URL(value, window.location.origin)
    return ['https:', 'http:'].includes(url.protocol) ? url.href : ''
  } catch {
    return ''
  }
}
export const outputText = (value: unknown) =>
  typeof value === 'string' ? value : JSON.stringify(value, null, 2)
export const fullCopy = (copy: {
  title: string
  bullets?: string[]
  description?: string
  keywords?: string[]
}) =>
  [copy.title, ...(copy.bullets || []), copy.description, (copy.keywords || []).join(', ')]
    .filter(Boolean)
    .join('\n\n')
