<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import client from '@/api/client'
import { useResource } from '@/composables/useResource'
import { useUserStore } from '@/stores/user'
import { useUiStore } from '@/stores/ui'
import { errorMessage } from '@/utils/format'
import type { ApiResponse, Provider } from '@/types'
import PageHeading from '@/components/ui/PageHeading.vue'
import PageState from '@/components/ui/PageState.vue'
import AppDialog from '@/components/ui/AppDialog.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
const user = useUserStore(),
  ui = useUiStore(),
  { data, loading, error, errorCode, reload } = useResource<{ items: Provider[] }>(
    '/providers',
    false,
  )
const open = ref(false),
  selected = ref<Provider | null>(null),
  busy = ref(false),
  failure = ref(''),
  testing = ref(''),
  testResults = reactive<Record<string, string>>({})
const form = reactive({
  name: '',
  key: '',
  model: '',
  embedding_model: 'text-embedding-v4',
  source: 'environment',
  replaceKey: false,
  isDefault: false,
})
const defaults: Record<string, string> = {
    llm: 'qwen-plus',
    image: 'qwen-image-3.0-pro',
    video: 'wan3.0-video',
  },
  types: Record<string, string> = { llm: '语言模型', image: '图片生成', video: '视频生成' }
const keyLabels: Record<string, string> = {
  empty: '未保存工作空间密钥',
  encrypted: '已加密保存',
  legacy: '旧格式 · 保存时加密',
  unavailable: '无法解密 · 请重新保存密钥',
}
const runtimeLabels: Record<string, string> = {
  pending: '待保存应用',
  ready: '配置可用于调用，连通性待测试',
  missing_key: '缺少可用凭据',
  invalid_config: '配置无效，请重新保存',
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
  const config = provider.effective_config || provider.config || {}
  Object.assign(form, {
    name: provider.name,
    key: '',
    model: String(config.model || defaults[provider.type] || ''),
    embedding_model: String(config.embedding_model || 'text-embedding-v4'),
    source:
      provider.configuration_status === 'pending' && provider.has_key
        ? 'stored'
        : String(config.credential_source || 'environment'),
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
  busy.value = true
  failure.value = ''
  try {
    await client.put(`/providers/${selected.value.id}`, {
      name: form.name.trim(),
      config: {
        model: form.model.trim(),
        credential_source: form.source,
        ...(selected.value.type === 'llm' ? { embedding_model: form.embedding_model.trim() } : {}),
      },
      is_default: form.isDefault ? 1 : 0,
      ...(form.replaceKey ? { api_key: form.key.trim() } : {}),
    })
    delete testResults[selected.value.id]
    const applied = form.isDefault
    open.value = false
    ui.notify(
      applied ? '配置已保存，后续新任务将使用此配置。' : '配置已保存为备用，可单独测试。',
      'info',
    )
    await reload()
  } catch (e) {
    failure.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
function refreshConfigurations() {
  for (const id of Object.keys(testResults)) delete testResults[id]
  void reload()
}
async function test(provider: Provider) {
  if (testing.value) return
  if (
    !(await ui.confirm(
      '测试所选配置',
      '将使用这条已保存配置的模型与凭据调用服务，可能产生费用。未保存的编辑不会用于测试。',
      '开始模型测试',
    ))
  )
    return
  testing.value = provider.id
  delete testResults[provider.id]
  try {
    const { data } = await client.post<
      ApiResponse<{ status: string; mode?: string; latency_ms?: number | null; model?: string }>
    >(`/providers/${provider.id}/test`)
    const result = data.data
    testResults[provider.id] =
      result.status === 'success'
        ? `${result.mode === 'Mock' ? '配置测试返回 · 模拟模式（未验证真实服务）' : '配置测试通过 · 真实 API'}${result.model ? ` · ${result.model}` : ''}${result.latency_ms != null ? ` · ${result.latency_ms} ms` : ''}`
        : '测试未通过，请检查此配置'
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
    description="配置当前工作空间的模型与凭据，测试所选服务。"
    eyebrow="MODEL SERVICES"
  >
    <button
      class="btn btn-secondary"
      :disabled="loading || !!testing || user.userInfo?.role !== 'admin'"
      @click="refreshConfigurations"
    >
      <AppIcon name="refresh" :size="16" />
      刷新配置
    </button>
  </PageHeading>
  <div class="notice mb-5">
    <AppIcon name="info" :size="19" />
    <span>
      保存并设为默认后，后续新任务使用此配置；运行中的任务保留启动时的配置。保存不调用模型，测试可能产生费用。
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
            <p class="text-muted text-sm">{{ types[provider.type] || provider.type }}</p>
          </div>
        </div>
        <div class="row wrap mt-4">
          <span class="badge" :class="provider.is_active ? 'status-success' : 'badge-neutral'">
            {{
              provider.configuration_status === 'pending'
                ? '待保存应用'
                : provider.is_active
                  ? '默认配置'
                  : '备用配置'
            }}
          </span>
        </div>
        <dl class="details-list">
          <div>
            <dt>配置模型</dt>
            <dd>{{ provider.effective_config?.model || provider.config?.model || '尚未指定' }}</dd>
          </div>
          <div>
            <dt>凭据来源</dt>
            <dd>
              {{
                (provider.effective_config || provider.config)?.credential_source === 'stored'
                  ? '当前工作空间的加密密钥'
                  : '服务端默认凭据'
              }}
            </dd>
          </div>
          <div>
            <dt>工作空间密钥</dt>
            <dd>{{ keyLabels[provider.key_status || ''] || '状态暂不可用' }}</dd>
          </div>
          <div>
            <dt>适配器</dt>
            <dd>{{ provider.adapter || '以服务端返回为准' }}</dd>
          </div>
        </dl>
        <p class="field-hint mb-4">
          {{ runtimeLabels[provider.runtime_status || ''] || '请刷新以获取配置状态' }}
        </p>
        <p v-if="provider.configuration_status === 'pending'" class="notice notice-warning">
          旧配置尚未应用，当前沿用服务端默认。请重新保存以确认模型与凭据来源。
        </p>
        <div class="row wrap">
          <button
            class="btn btn-secondary btn-sm"
            :disabled="
              !!testing ||
              provider.configuration_status !== 'applied' ||
              ['missing_key', 'invalid_config'].includes(provider.runtime_status || '')
            "
            @click="test(provider)"
          >
            <AppIcon name="wifi" :size="14" />
            {{ testing === provider.id ? '测试中…' : '测试所选配置' }}
          </button>
          <button class="btn btn-primary btn-sm" :disabled="!!testing" @click="start(provider)">
            <AppIcon name="settings" :size="14" />
            编辑配置
          </button>
        </div>
        <p v-if="testResults[provider.id]" class="provider-test-result" role="status">
          {{ testResults[provider.id] }}
        </p>
      </article>
    </div>
  </PageState>
  <AppDialog v-model="open" title="编辑模型配置" :busy="busy">
    <form id="provider-edit" class="form-stack" @submit.prevent="save">
      <p class="notice">API Key 加密保存且不回显。设为默认会影响后续新任务，备用配置可单独测试。</p>
      <p v-if="failure" class="notice notice-error" role="alert">{{ failure }}</p>
      <div class="form-group">
        <label for="provider-name">配置名称</label>
        <input
          id="provider-name"
          v-model="form.name"
          class="form-input"
          required
          maxlength="64"
          :disabled="busy"
        />
      </div>
      <div class="form-group">
        <label for="provider-model">模型 ID</label>
        <input
          id="provider-model"
          v-model="form.model"
          class="form-input"
          required
          maxlength="128"
          :disabled="busy"
        />
        <p class="field-hint">需使用当前适配器支持的模型；是否可调用以主动测试结果为准。</p>
      </div>
      <div v-if="selected?.type === 'llm'" class="form-group">
        <label for="provider-embedding">向量模型 ID</label>
        <input
          id="provider-embedding"
          v-model="form.embedding_model"
          class="form-input"
          required
          maxlength="128"
          :disabled="busy"
        />
        <p class="field-hint">
          向量模型需支持 1024
          维。更换后，旧模型的知识向量不会混入检索，需重新录入或重建；保存配置不会自动调用模型重建。
        </p>
      </div>
      <div class="form-group">
        <label for="provider-source">凭据来源</label>
        <select id="provider-source" v-model="form.source" class="form-select" :disabled="busy">
          <option value="environment">使用服务端默认凭据</option>
          <option value="stored">使用当前工作空间的密钥</option>
        </select>
      </div>
      <p v-if="selected?.key_status === 'legacy'" class="notice notice-warning">
        这条旧格式密钥会在保存时加密，无需重新填写。旧配置需保存后才应用。
      </p>
      <label class="checkbox-label">
        <input v-model="form.replaceKey" type="checkbox" :disabled="busy" />
        替换或清空工作空间 API Key
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
        <p class="field-hint">
          留空并保存会清除密钥。如果选择工作空间凭据，清空后不会自动改用服务端密钥。
        </p>
      </div>
      <label class="checkbox-label">
        <input v-model="form.isDefault" type="checkbox" :disabled="busy" />
        设为该类型默认配置
      </label>
    </form>
    <template #footer>
      <button class="btn btn-secondary" :disabled="busy" @click="open = false">取消</button>
      <button type="submit" form="provider-edit" class="btn btn-primary" :disabled="busy">
        {{ busy ? '保存中…' : '保存配置' }}
      </button>
    </template>
  </AppDialog>
</template>
