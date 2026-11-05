<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import client from '@/api/client'
import { useResource } from '@/composables/useResource'
import { useUserStore } from '@/stores/user'
import { useUiStore } from '@/stores/ui'
import { errorMessage, outputText } from '@/utils/format'
import type { ApiResponse, Provider } from '@/types'
import PageHeading from '@/components/ui/PageHeading.vue'
import PageState from '@/components/ui/PageState.vue'
import AppDialog from '@/components/ui/AppDialog.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
const user = useUserStore(),
  ui = useUiStore(),
  { data, loading, error, errorCode, reload } = useResource<{
    items: Provider[]
  }>('/providers', false),
  open = ref(false),
  selected = ref<Provider | null>(null),
  busy = ref(false),
  failure = ref(''),
  testing = ref(''),
  testResults = reactive<Record<string, string>>({})
const form = reactive({
    name: '',
    key: '',
    config: '',
    replaceKey: false,
    isDefault: false,
  }),
  types: Record<string, string> = {
    llm: '语言模型',
    image: '图片生成',
    video: '视频生成',
  }
watch(
  () => user.userInfo?.role,
  (role) => {
    if (role === 'admin') void reload()
  },
  { immediate: true },
)
function start(provider: Provider) {
  selected.value = provider
  Object.assign(form, {
    name: provider.name,
    key: '',
    config: outputText(provider.config || {}),
    replaceKey: false,
    isDefault: !!provider.is_default,
  })
  failure.value = ''
  open.value = true
}
watch(open, (value) => {
  if (!value) {
    form.key = ''
    selected.value = null
  }
})
async function save() {
  if (busy.value || !selected.value) return
  let config: Record<string, unknown>
  try {
    const parsed: unknown = JSON.parse(form.config)
    if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') throw new Error()
    config = parsed as Record<string, unknown>
  } catch {
    failure.value = '模型参数需为有效的 JSON 对象。'
    return
  }
  busy.value = true
  failure.value = ''
  try {
    await client.put(`/providers/${selected.value.id}`, {
      name: form.name.trim(),
      config,
      is_default: form.isDefault ? 1 : 0,
      ...(form.replaceKey ? { api_key: form.key.trim() } : {}),
    })
    open.value = false
    ui.notify('配置已保存到数据库，当前运行配置未改变。', 'info')
    await reload()
  } catch (e) {
    failure.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
async function test(provider: Provider) {
  if (testing.value) return
  if (
    !(await ui.confirm(
      '测试当前运行服务',
      '测试会调用服务端环境配置中的模型，可能产生费用。此操作不验证刚保存的数据库配置。',
      '开始模型测试',
    ))
  )
    return
  testing.value = provider.id
  delete testResults[provider.id]
  try {
    const { data } = await client.post<
      ApiResponse<{ status: string; mode?: string; latency_ms?: number | null }>
    >(`/providers/${provider.id}/test`)
    const result = data.data
    testResults[provider.id] =
      result.status === 'success'
        ? `运行服务测试通过 · ${result.mode === 'Mock' ? '模拟模式' : result.mode === 'Real API' ? '真实 API' : '模式未提供'}${result.latency_ms != null ? ` · ${result.latency_ms} ms` : ''}`
        : '测试未通过，请检查服务端配置'
  } catch (e) {
    testResults[provider.id] = `测试失败：${errorMessage(e)}`
  } finally {
    testing.value = ''
  }
}
</script>
<template>
  <PageHeading
    title="模型服务"
    description="管理模型配置记录，检查当前运行服务的连接情况。"
    eyebrow="MODEL SERVICES"
  >
    <button
      class="btn btn-secondary"
      :disabled="loading || user.userInfo?.role !== 'admin'"
      @click="reload()"
    >
      <AppIcon name="refresh" :size="16" />
      刷新配置
    </button>
  </PageHeading>
  <div class="notice notice-warning mb-5">
    <AppIcon name="info" :size="19" />
    <span>
      此处保存的是数据库配置记录；当前生成仍读取服务端环境配置。保存后不会自动生效，需由管理员在服务端应用并重启服务。
    </span>
  </div>
  <PageState
    :loading="loading"
    :error="user.userInfo?.role !== 'admin' ? '此页面需要管理员权限。' : error"
    :error-code="user.userInfo?.role !== 'admin' ? 403 : errorCode"
    :empty="!data?.items.length"
    title="尚无模型配置记录"
    description="请先在服务端初始化当前工作空间的厂商配置。"
    icon="spark"
    @retry="reload()"
  >
    <div class="three-grid">
      <article v-for="provider in data?.items" :key="provider.id" class="card provider-card">
        <div class="row">
          <span class="provider-mark">
            <AppIcon
              :name="
                provider.type === 'llm' ? 'spark' : provider.type === 'image' ? 'image' : 'video'
              "
              :size="23"
            />
          </span>
          <div>
            <h2>{{ provider.name }}</h2>
            <p class="text-muted text-sm">
              {{ types[provider.type] || provider.type }}
            </p>
          </div>
        </div>
        <dl class="details-list">
          <div>
            <dt>数据库凭据</dt>
            <dd>
              {{ provider.has_key ? '已保存凭据' : '未保存凭据' }}
              <span v-if="provider.has_key" class="code-pill">{{ provider.api_key_masked }}</span>
            </dd>
          </div>
          <div>
            <dt>记录中的模型</dt>
            <dd>{{ provider.config?.model || '尚未指定' }}</dd>
          </div>
          <div>
            <dt>当前运行状态</dt>
            <dd>以运行服务测试结果为准</dd>
          </div>
        </dl>
        <div class="row wrap">
          <button class="btn btn-secondary btn-sm" :disabled="!!testing" @click="test(provider)">
            <AppIcon name="wifi" :size="14" />
            {{ testing === provider.id ? '测试中…' : '测试运行服务' }}
          </button>
          <button class="btn btn-primary btn-sm" @click="start(provider)">
            <AppIcon name="settings" :size="14" />
            编辑记录
          </button>
        </div>
        <p v-if="testResults[provider.id]" class="provider-test-result" role="status">
          {{ testResults[provider.id] }}
        </p>
      </article>
    </div>
  </PageState>
  <AppDialog v-model="open" title="编辑模型配置记录" :busy="busy">
    <form id="provider-edit" class="form-stack" @submit.prevent="save">
      <p class="notice notice-warning">
        保存配置不会改变当前模型运行服务。当前后端未加密保存此处凭据，请仅在本地测试时使用测试密钥；生产密钥请通过服务端环境配置管理。
      </p>
      <p v-if="failure" class="notice notice-error" role="alert">
        {{ failure }}
      </p>
      <div class="form-group">
        <label for="provider-name">配置名称</label>
        <input
          id="provider-name"
          v-model="form.name"
          class="form-input"
          required
          :disabled="busy"
        />
      </div>
      <label class="checkbox-label">
        <input v-model="form.replaceKey" type="checkbox" :disabled="busy" />
        替换数据库中的 API Key
      </label>
      <div v-if="form.replaceKey" class="form-group">
        <label for="provider-key">新 API Key</label>
        <input
          id="provider-key"
          v-model="form.key"
          class="form-input"
          type="password"
          autocomplete="new-password"
          :disabled="busy"
        />
        <p class="field-hint">留空并保存将清除该记录的密钥。</p>
      </div>
      <div class="form-group">
        <label for="provider-config">模型参数（JSON）</label>
        <textarea
          id="provider-config"
          v-model="form.config"
          class="form-textarea"
          rows="6"
          required
          spellcheck="false"
          :disabled="busy"
        />
      </div>
      <label class="checkbox-label">
        <input v-model="form.isDefault" type="checkbox" :disabled="busy" />
        标记为默认配置记录
      </label>
    </form>
    <template #footer>
      <button class="btn btn-secondary" :disabled="busy" @click="open = false">取消</button>
      <button type="submit" form="provider-edit" class="btn btn-primary" :disabled="busy">
        {{ busy ? '保存中…' : '保存配置记录' }}
      </button>
    </template>
  </AppDialog>
</template>
