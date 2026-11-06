import { test, expect } from '@playwright/test'
import { setup, ready, noOverflow, paths, task, copy } from './fixtures'

test('登录失败、密码切换、记住邮箱、登录返回原页及退出', async ({ page }) => {
  const h = await setup(page, { auth: false })
  let attempts = 0
  h.handler = async (route, path) => {
    if (path !== '/auth/login') return false
    attempts++
    await route.fulfill(
      attempts === 1
        ? { status: 401, json: { detail: '邮箱或密码错误' } }
        : {
            json: {
              code: 200,
              data: { access_token: 'qa-auth-token' },
              message: 'ok',
            },
          },
    )
    return true
  }
  await page.goto('/assets?type=image')
  await expect(page).toHaveURL(/login\?redirect=/)
  await page.getByLabel('工作邮箱').fill('qa@example.test')
  await page.getByLabel('登录密码', { exact: true }).fill('test-password')
  await page.getByRole('button', { name: '显示密码' }).click()
  await expect(page.getByLabel('登录密码', { exact: true })).toHaveAttribute('type', 'text')
  await page.getByRole('checkbox', { name: '记住邮箱' }).check()
  await page.getByRole('button', { name: '登录工作空间' }).click()
  await expect(page.getByRole('alert')).toContainText('邮箱或密码不正确')
  await page.getByRole('button', { name: '登录工作空间' }).click()
  await expect(page).toHaveURL(/\/assets\?type=image/)
  expect(await page.evaluate(() => localStorage.getItem('remembered-email'))).toBe(
    'qa@example.test',
  )
  await page.getByRole('button', { name: '退出登录' }).click()
  await expect(page).toHaveURL(/\/login$/)
  expect(await page.evaluate(() => localStorage.getItem('token'))).toBeNull()
})

test('401 统一清理身份并保留返回路径', async ({ page }) => {
  const h = await setup(page)
  await page.goto('/skus')
  await ready(page)
  h.handler = async (route, path) => {
    if (path !== '/skus') return false
    await route.fulfill({ status: 401, json: { detail: 'Session expired' } })
    return true
  }
  await page.getByRole('button', { name: '刷新', exact: true }).click()
  await expect(page).toHaveURL(/\/login\?redirect=%2Fskus/)
  expect(await page.evaluate(() => localStorage.getItem('token'))).toBeNull()
})

test('管理员菜单与直接路由权限，接口 403 状态', async ({ page }) => {
  const h = await setup(page, { role: 'operator' })
  await page.goto('/dashboard')
  await ready(page)
  await expect(page.locator('.sidebar').getByRole('link', { name: '模型服务' })).toHaveCount(0)
  await page.goto('/providers')
  await expect(page).toHaveURL(/\/forbidden$/)
  await expect(page.getByRole('heading', { name: '暂无访问权限' })).toBeVisible()
  h.handler = async (route, path) => {
    if (path !== '/assets') return false
    await route.fulfill({ status: 403, json: { detail: 'Forbidden' } })
    return true
  }
  await page.goto('/assets')
  await expect(page.getByRole('heading', { name: '暂无访问权限' })).toBeVisible()
})

test('页面搜索、键盘选择、弹窗 Escape 与焦点恢复', async ({ page }) => {
  await setup(page)
  await page.goto('/tasks')
  await ready(page)
  await page.keyboard.press('Control+k')
  const finder = page.getByRole('dialog', { name: '快速前往' })
  await expect(finder).toBeVisible()
  await finder.getByLabel('搜索功能页面').fill('素材')
  await page.keyboard.press('ArrowDown')
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/\/assets$/)
  await page.goto('/skus')
  const trigger = page.getByRole('button', { name: '录入新商品', exact: true })
  await trigger.click()
  const dialog = page.getByRole('dialog', { name: '录入新商品' })
  await expect(dialog).toBeVisible()
  for (let i = 0; i < 28; i++) {
    await page.keyboard.press('Tab')
    expect(
      await page.evaluate(() => !!document.activeElement?.closest('dialog[open]')),
    ).toBeTruthy()
  }
  await page.keyboard.press('Escape')
  await expect(dialog).not.toBeVisible()
  await expect(trigger).toBeFocused()
})

test('服务端筛选分页、筛选回到第一页与过期响应取消', async ({ page }) => {
  const h = await setup(page)
  await page.goto('/skus')
  await ready(page)
  await page.getByRole('button', { name: '下一页', exact: true }).click()
  await expect
    .poll(() =>
      h.requests
        .filter((r) => r.path === '/skus')
        .at(-1)
        ?.query.get('page'),
    )
    .toBe('2')
  await page.getByRole('searchbox').fill('newest')
  await expect
    .poll(() =>
      h.requests
        .filter((r) => r.path === '/skus')
        .at(-1)
        ?.query.get('q'),
    )
    .toBe('newest')
  expect(
    h.requests
      .filter((r) => r.path === '/skus')
      .at(-1)
      ?.query.get('page'),
  ).toBe('1')
  h.handler = async (route, path) => {
    if (path !== '/skus' || new URL(route.request().url()).searchParams.get('q') !== 'older')
      return false
    await new Promise((resolve) => setTimeout(resolve, 1000))
    try {
      await route.fulfill({
        json: {
          data: {
            items: [{ id: 'old', name: 'STALE RESPONSE', code: 'STALE' }],
            total: 1,
          },
        },
      })
    } catch {}
    return true
  }
  await page.getByRole('searchbox').fill('older')
  await page.waitForTimeout(400)
  await page.getByRole('searchbox').fill('current')
  await expect(page.getByRole('heading', { name: 'current 1', exact: true })).toBeVisible()
  await page.waitForTimeout(1000)
  await expect(page.getByText('STALE RESPONSE')).toHaveCount(0)
})

test('商品不预填规格，创建任务限制配置、防重复提交并进入工作台', async ({ page }) => {
  const h = await setup(page)
  let posts = 0
  let releaseSubmission!: () => void
  const gate = new Promise<void>((resolve) => {
    releaseSubmission = resolve
  })
  h.handler = async (route, path) => {
    if (path !== '/tasks' || route.request().method() !== 'POST') return false
    posts++
    await gate
    await route.fulfill({
      json: { code: 200, data: { task_id: task.id }, message: 'ok' },
    })
    return true
  }
  await page.goto('/skus?new=1')
  const skuDialog = page.getByRole('dialog', { name: '录入新商品' })
  await expect(skuDialog).toBeVisible()
  await expect(skuDialog.getByPlaceholder('真实数值')).toHaveCount(0)
  await page.keyboard.press('Escape')
  await page.goto('/tasks?new=1')
  const dialog = page.getByRole('dialog', { name: '开始一次新创作' })
  await expect(dialog).toBeVisible()
  await dialog.getByRole('radio').first().check()
  await dialog.getByLabel('搜索可选商品').fill('find')
  await expect
    .poll(() =>
      h.requests
        .filter((r) => r.path === '/skus')
        .at(-1)
        ?.query.get('q'),
    )
    .toBe('find')
  await dialog.getByRole('button', { name: '下一页', exact: true }).click()
  await expect
    .poll(() =>
      h.requests
        .filter((r) => r.path === '/skus')
        .at(-1)
        ?.query.get('page'),
    )
    .toBe('2')
  await dialog.getByLabel('审核未通过时的重试上限').selectOption('0')
  const start = dialog.locator('button[form=task-create-form][type=submit]')
  await start.click()
  await expect(start).toBeDisabled()
  await page.keyboard.press('Escape')
  await expect(dialog).toBeVisible()
  await page.locator('#task-create-form').evaluate((form) => {
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
  })
  releaseSubmission()
  await expect(page).toHaveURL(/\/workbench\/task-1$/)
  expect(posts).toBe(1)
  expect(h.writes.find((r) => r.path === '/tasks')?.body.config).toEqual({
    language: 'en',
    platform: 'amazon',
    media_type: 'both',
    max_retries: 0,
  })
})

test('文案安全文本渲染、编辑保存后提示重新审核', async ({ page }) => {
  const h = await setup(page)
  h.handler = async (route, path) => {
    if (path !== '/copies/copy-1' || route.request().method() !== 'PUT') return false
    await route.fulfill({
      json: { code: 200, data: { id: 'copy-1' }, message: 'saved' },
    })
    return true
  }
  await page.goto('/copies')
  await ready(page)
  await expect(page.getByRole('heading', { name: copy.title, exact: true })).toBeVisible()
  expect(
    await page.evaluate(() => (window as unknown as { unsafeOutput?: boolean }).unsafeOutput),
  ).toBeUndefined()
  await page.getByRole('button', { name: '编辑', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '编辑文案' })
  await expect(dialog.getByLabel('核心卖点 · 每行一条')).toHaveValue(
    'First verified benefit\nSecond verified benefit',
  )
  await dialog.getByLabel('商品标题').fill('Updated title')
  await dialog.getByRole('button', { name: '保存并标记待审核' }).click()
  await expect(
    page.getByText('文案已保存，需要重新审核后才能交付。', { exact: true }),
  ).toBeVisible()
  expect(h.writes[0].body.bullets).toEqual(copy.bullets)
})

test('真实零值、费用分布隐藏、刊登与 ZIP 入口禁用', async ({ page }) => {
  const h = await setup(page, { mode: 'empty' })
  await page.goto('/dashboard')
  await ready(page)
  await expect(page.locator('.metric-number').first()).toHaveText(/^0\s*件$/)
  await expect(page.locator('.metric-number').last()).toHaveText('$0.0000')
  h.mode = 'full'
  await page.goto('/audit')
  await ready(page)
  await expect(page.getByText('DO NOT RENDER')).toHaveCount(0)
  await page.goto('/packages')
  await ready(page)
  await expect(page.getByRole('button', { name: 'ZIP 下载尚未开放' })).toBeDisabled()
  await page.goto('/listings')
  await ready(page)
  await expect(page.getByRole('button', { name: '发布到平台 · 尚未开放' })).toBeDisabled()
  await expect(page.getByText('已登记（本地记录）', { exact: true })).toBeVisible()
  expect(h.writes).toHaveLength(0)
})

test('媒体失效、预览与知识检索必须主动触发', async ({ page }) => {
  const h = await setup(page)
  await page.goto('/assets')
  await ready(page)
  await expect(page.getByText('媒体暂时无法加载').first()).toBeVisible()
  await page.getByRole('button', { name: '查看素材' }).last().click()
  const dialog = page.getByRole('dialog', { name: '素材预览' })
  await expect(dialog.getByText('媒体暂时无法加载')).toBeVisible()
  await page.keyboard.press('Escape')
  await page.goto('/knowledge')
  await ready(page)
  expect(h.writes).toHaveLength(0)
  await page.getByLabel('知识检索问题').fill('品牌规范')
  await page.getByRole('button', { name: '开始检索' }).click()
  await expect(page.getByRole('alert')).toContainText('此请求已被自动化拦截')
  expect(h.writes.map((r) => r.path)).toEqual(['/knowledge/query'])
})

test('工作台鉴权、断线轮询、有限重连和离开时清理', async ({ page }) => {
  test.setTimeout(45000)
  const h = await setup(page, { status: 'running' })
  h.disconnect = true
  await page.goto('/workbench/task-1')
  await ready(page)
  await expect.poll(() => h.wsAuth).toBeGreaterThan(0)
  const count = () => h.requests.filter((r) => r.path === '/tasks/task-1').length,
    initial = count()
  await expect.poll(count, { timeout: 7000 }).toBeGreaterThan(initial)
  await expect(page.getByText('连接中断，将定时刷新', { exact: true })).toBeVisible()
  const connections = h.wsConnections
  await page.getByRole('link', { name: '返回任务', exact: true }).click()
  const after = count()
  await page.waitForTimeout(5500)
  expect(count()).toBe(after)
  expect(h.wsConnections).toBe(connections)
  h.disconnect = false
  await page.goto('/workbench/task-2')
  await ready(page)
  await expect(page.getByText('实时连接正常', { exact: true })).toBeVisible()
  await page.waitForTimeout(400)
  const fresh = () => h.requests.filter((r) => r.path === '/tasks/task-2').length,
    n = fresh()
  await page.waitForTimeout(5100)
  expect(fresh()).toBeGreaterThan(n)
})

test('任务提交响应丢失后复用请求标识，修改表单后使用新标识', async ({ page }) => {
  const h = await setup(page)
  const keys: string[] = []
  h.handler = async (route, path) => {
    if (path !== '/tasks' || route.request().method() !== 'POST') return false
    keys.push(route.request().headers()['idempotency-key'])
    if (keys.length < 3) await route.abort('failed')
    else
      await route.fulfill({
        json: { code: 200, data: { task_id: 'task-1', status: 'pending' }, message: 'ok' },
      })
    return true
  }
  await page.goto('/tasks?new=1')
  const dialog = page.getByRole('dialog', { name: '开始一次新创作' })
  await dialog.getByRole('radio').first().check()
  const submit = dialog.locator('button[form=task-create-form][type=submit]')
  await submit.click()
  await expect(dialog.getByRole('alert')).toBeVisible()
  await submit.click()
  await expect.poll(() => keys.length).toBe(2)
  await expect(submit).toBeEnabled()
  await dialog.getByLabel('审核未通过时的重试上限').selectOption('0')
  await submit.click()
  await expect(page).toHaveURL(/\/workbench\/task-1$/)
  expect(keys[0]).toBeTruthy()
  expect(keys[0]).toBe(keys[1])
  expect(keys[2]).not.toBe(keys[1])
})

test('排队任务说明恢复行为，中断任务显示原因并在确认后重新排队', async ({ page }) => {
  const h = await setup(page, { status: 'pending' })
  let error = ''
  h.handler = async (route, path) => {
    if (path === '/tasks/task-1' && route.request().method() === 'GET') {
      await route.fulfill({
        json: {
          code: 200,
          data: { task: { ...task, status: h.status, error_message: error }, assets: [] },
          message: 'ok',
        },
      })
      return true
    }
    if (path === '/tasks/task-1/run') {
      expect(route.request().headers()['idempotency-key']).toBeTruthy()
      h.status = 'pending'
      error = ''
      await route.fulfill({
        json: { code: 200, data: { task_id: 'task-1', status: 'pending' }, message: 'ok' },
      })
      return true
    }
    return false
  }
  await page.goto('/workbench/task-1')
  await expect(
    page.getByText('任务已保存，正在排队。尚未开始的任务会在服务恢复后继续执行。'),
  ).toBeVisible()
  await expect(page.getByRole('button', { name: '重新生成', exact: true })).toHaveCount(0)
  h.status = 'failed'
  error = '执行因数据库连接中断而终止。模型请求可能已经产生费用；系统未自动重跑。'
  await page.getByRole('button', { name: '刷新任务' }).click()
  await expect(page.getByText(error)).toBeVisible()
  await page.getByRole('button', { name: '重新生成', exact: true }).click()
  const confirm = page.getByRole('dialog', { name: '重新执行这个任务' })
  await expect(confirm).toContainText('再次产生模型费用')
  expect(h.writes).toHaveLength(0)
  await confirm.getByRole('button', { name: '重新生成', exact: true }).click()
  await expect(
    page.getByText('任务已保存，正在排队。尚未开始的任务会在服务恢复后继续执行。'),
  ).toBeVisible()
  expect(h.writes.map((request) => request.path)).toEqual(['/tasks/task-1/run'])
})

for (const mode of ['full', 'empty', 'error'] as const)
  for (const width of [1440, 1024, 390, 360]) {
    test(`所有页面 ${mode} 状态，${width}px 无横向溢出`, async ({ page }) => {
      test.setTimeout(60000)
      await page.setViewportSize({ width, height: 900 })
      const errors: string[] = []
      page.on('pageerror', (error) => errors.push(error.message))
      const h = await setup(page, { mode })
      for (const path of paths) {
        await page.goto(path)
        await ready(page)
        await noOverflow(page)
        if (mode === 'error')
          await expect(page.getByText(/暂时无法加载|部分数据暂不可用/).first()).toBeVisible()
      }
      await page.goto('/login')
      await expect(page.getByRole('heading', { name: '欢迎回到创作现场' })).toBeVisible()
      await noOverflow(page)
      expect(errors).toEqual([])
      expect(h.writes).toHaveLength(0)
    })
  }

test('手机导航抽屉焦点、Escape 恢复与页面搜索', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 })
  await setup(page)
  await page.goto('/dashboard')
  await ready(page)
  const trigger = page.getByRole('button', { name: '打开导航' })
  await trigger.click()
  await expect(page.locator('.sidebar')).toHaveClass(/sidebar-open/)
  for (let i = 0; i < 18; i++) {
    await page.keyboard.press('Tab')
    expect(await page.evaluate(() => !!document.activeElement?.closest('.sidebar'))).toBeTruthy()
  }
  await page.keyboard.press('Escape')
  await expect(trigger).toBeFocused()
  await page.keyboard.press('Control+k')
  await page.getByRole('dialog', { name: '快速前往' }).getByLabel('搜索功能页面').fill('设置')
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/\/settings$/)
})

test('租户模型配置保存生效，所选配置付费测试需主动确认', async ({ page }) => {
  const h = await setup(page)
  h.handler = async (route, path) => {
    if (path === '/providers/provider-1' && route.request().method() === 'PUT') {
      await route.fulfill({
        json: { code: 200, data: { id: 'provider-1' }, message: 'saved' },
      })
      return true
    }
    if (path === '/providers/provider-1/test') {
      await route.fulfill({
        json: {
          code: 200,
          data: { status: 'success', mode: 'Mock', latency_ms: null },
          message: 'QA only',
        },
      })
      return true
    }
    return false
  }
  await page.goto('/providers')
  await ready(page)
  expect(h.writes).toHaveLength(0)
  await page.getByRole('button', { name: '编辑配置' }).click()
  const dialog = page.getByRole('dialog', { name: '编辑模型配置' })
  await dialog.getByLabel('配置名称').fill('Offline model service')
  await dialog.getByRole('button', { name: '保存配置' }).click()
  await expect(
    page.getByText('配置已保存，后续新任务将使用此配置。', { exact: true }),
  ).toBeVisible()
  expect(h.writes[0].body).not.toHaveProperty('api_key')
  await page.getByRole('button', { name: '测试所选配置' }).click()
  const confirm = page.getByRole('dialog', { name: '测试所选配置' })
  await expect(confirm).toContainText('可能产生费用')
  expect(h.writes).toHaveLength(1)
  await confirm.getByRole('button', { name: '开始模型测试' }).click()
  await expect(
    page.getByText('配置测试返回 · 模拟模式（未验证真实服务）', { exact: true }),
  ).toBeVisible()
  expect(h.writes[1].path).toBe('/providers/provider-1/test')
  await page.getByRole('button', { name: '编辑配置' }).click()
  await dialog.getByLabel('配置名称').fill('Updated offline model')
  await dialog.getByRole('button', { name: '保存配置', exact: true }).click()
  await expect(
    page.getByText('配置测试返回 · 模拟模式（未验证真实服务）', { exact: true }),
  ).toHaveCount(0)
})

test('交付清单展示接口返回内容，独立审核不自动调用模型', async ({ page }) => {
  const h = await setup(page)
  h.handler = async (route, path) => {
    if (path !== '/packages/export') return false
    await route.fulfill({
      json: {
        code: 200,
        data: {
          task_id: task.id,
          sku_id: task.sku_id,
          copywriting: copy,
          media_assets: [{ type: 'image', url: 'javascript:alert(1)' }],
          quality_audit: { score: 92, passed: 1, suggestions: [] },
          download_archive_url: null,
        },
        message: 'manifest',
      },
    })
    return true
  }
  await page.goto('/packages')
  await ready(page)
  await page.getByRole('button', { name: '查看交付清单' }).click()
  const dialog = page.getByRole('dialog', { name: '交付清单' })
  await expect(dialog.getByRole('heading', { name: copy.title })).toBeVisible()
  await expect(dialog.getByRole('link', { name: '打开文件' })).toHaveCount(0)
  await expect(dialog.getByRole('button', { name: '下载 ZIP · 尚未开放' })).toBeDisabled()
  await page.keyboard.press('Escape')
  await page.goto('/compliance')
  await ready(page)
  await page.getByRole('button', { name: '检查一段文案' }).click()
  await expect(page.getByRole('dialog', { name: '检查文案' })).toContainText('可能产生费用')
  expect(h.writes.map((r) => r.path)).toEqual(['/packages/export'])
})

test('工作台自动重连达到上限后停止，可手动恢复', async ({ page }) => {
  const h = await setup(page, { status: 'running' })
  h.disconnect = true
  await page.clock.install()
  await page.goto('/workbench/task-1')
  await ready(page)
  await expect.poll(() => h.wsConnections).toBe(1)
  for (const delay of [1000, 2000, 4000, 8000, 15000]) {
    await expect(page.getByText('连接中断，将定时刷新', { exact: true })).toBeVisible()
    const before = h.wsConnections
    await page.clock.fastForward(delay + 150)
    await expect.poll(() => h.wsConnections).toBe(before + 1)
  }
  await expect(page.getByText('重连已暂停，正在定时刷新', { exact: true })).toBeVisible()
  await page.clock.fastForward(60000)
  expect(h.wsConnections).toBe(6)
  h.disconnect = false
  await page.getByRole('button', { name: '重新连接', exact: true }).click()
  await expect(page.getByText('实时连接正常', { exact: true })).toBeVisible()
})

test('模型编辑可选择工作空间凭据，关闭后清除输入密钥', async ({ page }) => {
  const h = await setup(page)
  h.handler = async (route, path) => {
    if (path === '/providers/provider-1' && route.request().method() === 'PUT') {
      await route.fulfill({ json: { code: 200, data: { id: 'provider-1' }, message: 'saved' } })
      return true
    }
    return false
  }
  await page.goto('/providers')
  await ready(page)
  await page.getByRole('button', { name: '编辑配置' }).click()
  const dialog = page.getByRole('dialog', { name: '编辑模型配置' })
  await dialog.getByLabel('配置名称').fill('Offline configured model')
  await dialog.getByLabel('模型 ID', { exact: true }).fill('offline-model')
  await dialog.getByLabel('凭据来源').selectOption('stored')
  await dialog.getByRole('checkbox', { name: '替换或清空工作空间 API Key' }).check()
  await dialog.getByLabel('新 API Key').fill('offline-sensitive-test-key')
  await dialog.getByRole('checkbox', { name: '设为该类型默认配置' }).uncheck()
  await dialog.getByRole('button', { name: '保存配置', exact: true }).click()
  await expect(page.getByText('配置已保存为备用，可单独测试。', { exact: true })).toBeVisible()
  expect(h.writes[0].body.config).toEqual({
    model: 'offline-model',
    credential_source: 'stored',
    embedding_model: 'text-embedding-v4',
  })
  expect(h.writes[0].body.api_key).toBe('offline-sensitive-test-key')
  expect(h.writes[0].body.is_default).toBe(0)
  expect(await page.evaluate(() => JSON.stringify(localStorage))).not.toContain(
    'offline-sensitive-test-key',
  )
  await page.getByRole('button', { name: '编辑配置' }).click()
  await dialog.getByRole('checkbox', { name: '替换或清空工作空间 API Key' }).check()
  await expect(dialog.getByLabel('新 API Key')).toBeEmpty()
})
