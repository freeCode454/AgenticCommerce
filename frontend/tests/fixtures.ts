import { expect, type Page, type Route } from '@playwright/test'

export const paths = [
  '/dashboard',
  '/skus',
  '/tasks',
  '/batches',
  '/assets',
  '/copies',
  '/compliance',
  '/knowledge',
  '/providers',
  '/packages',
  '/listings',
  '/audit',
  '/settings',
  '/workbench/task-1',
]
export const longName = '可重复使用的便携产品与超长商品名称验收'.repeat(8)
export const sku = {
  id: 'sku-1',
  code: 'QA-001',
  name: longName,
  category: '户外运动',
  description: '真实接口契约的测试夹具，仅用于自动化验收。',
  specs: { 材质: '经核实材质' },
  images: [],
  create_time: '2026-11-01T10:30:00',
}
export const task = {
  id: 'task-1',
  sku_id: sku.id,
  sku_code: sku.code,
  sku_name: longName,
  status: 'completed',
  create_time: sku.create_time,
}
export const copy = {
  id: 'copy-1',
  task_id: task.id,
  sku_name: longName,
  title: '<img src=x onerror="window.unsafeOutput=true"> Safe product title',
  bullets: ['First verified benefit', 'Second verified benefit'],
  description: 'Product description\nSecond paragraph',
  keywords: ['travel', 'everyday'],
  language: 'en',
  status: 'draft',
  create_time: sku.create_time,
}
export const report = {
  id: 'report-1',
  task_id: task.id,
  sku_name: longName,
  score: 92,
  passed: 1,
  status: 'passed',
  dimensions: { accuracy: 92 },
  violations: [],
  suggestions: ['核实商品描述'],
  create_time: sku.create_time,
}
export const assets = [
  {
    id: 'asset-1',
    type: 'image',
    sub_type: 'main',
    sku_name: longName,
    url: '/qa-broken-image.png',
    is_mock: 0,
  },
  {
    id: 'asset-2',
    type: 'video',
    sub_type: 'product_showcase',
    sku_name: longName,
    url: '/qa-broken-video.mp4',
    is_mock: 0,
  },
]
export interface Harness {
  mode: 'full' | 'empty' | 'error'
  role: string
  status: string
  requests: { path: string; method: string; query: URLSearchParams }[]
  writes: { path: string; body: Record<string, unknown> }[]
  handler?: (route: Route, path: string) => Promise<boolean>
  wsConnections: number
  wsClosed: number
  wsAuth: number
  disconnect: boolean
}
export async function setup(
  page: Page,
  {
    auth = true,
    mode = 'full',
    role = 'admin',
    status = 'completed',
  }: {
    auth?: boolean
    mode?: Harness['mode']
    role?: string
    status?: string
  } = {},
) {
  const h: Harness = {
    mode,
    role,
    status,
    requests: [],
    writes: [],
    wsConnections: 0,
    wsClosed: 0,
    wsAuth: 0,
    disconnect: false,
  }
  await page.addInitScript((logged) => {
    if (!sessionStorage.getItem('qa-initialized')) {
      if (logged) localStorage.setItem('token', 'qa-session')
      else localStorage.removeItem('token')
      sessionStorage.setItem('qa-initialized', '1')
    }
  }, auth)
  await page.route('**/qa-broken-*', (route) => route.fulfill({ status: 404, body: '' }))
  await page.routeWebSocket('**/api/v1/ws/tasks/**', (ws) => {
    h.wsConnections++
    ws.onClose(() => h.wsClosed++)
    ws.onMessage((message) => {
      if (message === 'ping') {
        ws.send('pong')
        return
      }
      const value = JSON.parse(String(message))
      if (value.type === 'authenticate') {
        h.wsAuth++
        if (h.disconnect) ws.close({ code: 1011, reason: 'QA disconnected' })
        else ws.send(JSON.stringify({ type: 'authenticated' }))
      }
    })
  })
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request(),
      url = new URL(request.url()),
      path = url.pathname.replace('/api/v1', ''),
      method = request.method()
    h.requests.push({ path, method, query: url.searchParams })
    if (!['GET', 'HEAD'].includes(method))
      h.writes.push({ path, body: request.postDataJSON() || {} })
    if (h.handler && (await h.handler(route, path))) return
    const send = (data: unknown) =>
      route.fulfill({ json: { code: 200, data, message: 'QA fixture' } })
    if (path === '/auth/me')
      return send({
        user_id: 'qa-user',
        name: '验收用户',
        email: 'qa@example.test',
        role: h.role,
        tenant_id: 'qa-tenant',
        tenant_name: '自动化验收工作空间',
      })
    // Never forward a mutation or model request to the actual API.
    if (method !== 'GET')
      return route.fulfill({
        status: 418,
        json: { detail: '此请求已被自动化拦截，未调用真实服务。' },
      })
    if (h.mode === 'error')
      return route.fulfill({
        status: 503,
        json: { detail: '验收服务暂不可用' },
      })
    const empty = h.mode === 'empty'
    if (path === '/audit/costs')
      return send({
        total_runs: empty ? 0 : 7,
        total_prompt_tokens: empty ? 0 : 1600,
        total_completion_tokens: empty ? 0 : 400,
        total_tokens: empty ? 0 : 2000,
        total_cost_usd: empty ? 0 : 0.012,
        breakdown_by_model: [{ model: 'DO NOT RENDER', cost: 999 }],
      })
    if (path === '/system/status')
      return send({
        tenant_id: 'qa-tenant',
        tenant_name: '自动化验收工作空间',
        dependencies: empty ? {} : { postgres: 'ready', redis: 'ready', storage: 'unavailable' },
      })
    if (path === '/providers')
      return send({
        items: empty
          ? []
          : [
              {
                id: 'provider-1',
                type: 'llm',
                name: longName,
                has_key: false,
                config: { model: 'qa-model' },
                is_default: 1,
              },
            ],
      })
    if (path === '/tasks/task-1' || path === '/tasks/task-2')
      return send({
        task: { ...task, id: path.split('/').pop(), status: h.status },
        copy: empty ? null : copy,
        assets: empty ? [] : assets,
        compliance_report: empty ? null : report,
      })
    if (path.match(/^\/tasks\/[^/]+\/nodes$/))
      return send({
        items: empty
          ? []
          : [
              {
                id: 'node-1',
                node_name: 'orchestrator',
                status: 'success',
                elapsed_ms: 42,
                input_data: { sku_id: sku.id },
                output_data: { ready: true },
              },
              {
                id: 'node-2',
                node_name: 'quality_reviewer',
                status: 'failed',
                elapsed_ms: 3000,
                output_data: { error: '需要核实材质描述' },
              },
            ],
      })
    if (path === '/copies/copy-1') return send(copy)
    if (path === '/compliance/reports/report-1') return send(report)
    if (path === '/knowledge/docs/doc-1')
      return send({
        id: 'doc-1',
        name: longName,
        category: 'brand',
        vector_status: 'indexed',
        chunks: [{ id: 'chunk-1', index: 1, content: '品牌语调需保持清晰可信。' }],
      })
    if (path === '/batches/batch-1')
      return send({ batch: { id: 'batch-1', name: longName }, tasks: [task] })
    const records: Record<string, unknown[]> = {
      '/skus': Array.from({ length: 25 }, (_, i) => ({
        ...sku,
        id: `sku-${i + 1}`,
        code: `QA-${i + 1}`,
        name: url.searchParams.get('q')
          ? `${url.searchParams.get('q')} ${i + 1}`
          : `${longName} ${i + 1}`,
      })),
      '/tasks': [task],
      '/assets': assets,
      '/copies': [copy],
      '/compliance/reports': [report],
      '/batches': [
        {
          id: 'batch-1',
          name: longName,
          total_count: 1,
          status: 'pending',
          create_time: sku.create_time,
        },
      ],
      '/knowledge/docs': [
        {
          id: 'doc-1',
          name: longName,
          category: 'brand',
          doc_type: 'brand',
          vector_status: 'pending',
          create_time: sku.create_time,
        },
      ],
      '/packages': [
        {
          task_id: task.id,
          sku_name: longName,
          sku_code: sku.code,
          create_time: sku.create_time,
        },
      ],
      '/listings': [
        {
          id: 'listing-1',
          sku_name: longName,
          sku_code: sku.code,
          platform: 'amazon',
          status: 'published',
          listing_data: { external_product_id: 'LOCAL_ONLY' },
          create_time: sku.create_time,
        },
      ],
      '/audit/logs': [
        {
          id: 'log-1',
          user_name: '验收用户',
          action: 'create_task',
          target_id: task.id,
          target_type: 'task',
          detail: { status: 'created' },
          create_time: sku.create_time,
        },
      ],
    }
    if (path in records) {
      const all = empty ? [] : records[path],
        pageNumber = Number(url.searchParams.get('page') || 1),
        size = Number(url.searchParams.get('page_size') || 10),
        items = all.slice((pageNumber - 1) * size, pageNumber * size)
      return send(
        path === '/packages' ? { items, count: items.length } : { items, total: all.length },
      )
    }
    return route.fulfill({
      status: 404,
      json: { detail: `Unknown QA route: ${method} ${path}` },
    })
  })
  return h
}
export async function ready(page: Page) {
  await expect(page.locator('main h1')).toBeVisible()
  await expect(page.getByRole('status', { name: '正在加载' })).toHaveCount(0)
}
export async function noOverflow(page: Page) {
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1),
  ).toBeTruthy()
}
