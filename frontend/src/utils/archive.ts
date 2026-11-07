import axios from 'axios'
import client from '@/api/client'
import { errorMessage } from './format'

const apiPrefix = '/api/v1'
type ArchiveKind = 'asset' | 'package'

export function archivePath(value?: string, kind: ArchiveKind = 'asset'): string {
  if (!value) return ''
  const path = value.startsWith(window.location.origin)
    ? value.slice(window.location.origin.length)
    : value
  const pattern = kind === 'asset'
    ? /^\/api\/v1\/assets\/[\w-]+\/file$/
    : /^\/api\/v1\/packages\/[\w-]+\/download$/
  return pattern.test(path) ? path.slice(apiPrefix.length) : ''
}

export function fetchArchive(value: string, kind: ArchiveKind, signal?: AbortSignal) {
  const path = archivePath(value, kind)
  if (!path) throw new Error('归档地址无效')
  return client.get<Blob>(path, { responseType: 'blob', timeout: 120_000, signal })
}

export async function saveArchive(value: string, kind: ArchiveKind) {
  const { data, headers } = await fetchArchive(value, kind)
  const filename = /filename="([\w.-]+)"/.exec(String(headers['content-disposition']))?.[1]
  const url = URL.createObjectURL(data)
  const link = document.createElement('a')
  link.href = url
  link.download = filename || 'download'
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export async function archiveErrorMessage(error: unknown): Promise<string> {
  if (axios.isAxiosError(error) && error.response?.data instanceof Blob) {
    try {
      const body = JSON.parse(await error.response.data.text())
      if (typeof body?.detail === 'string') return body.detail
    } catch {
      // Let the standard error handling cover non-JSON responses.
    }
  }
  return errorMessage(error, '下载失败，请稍后重试。')
}
