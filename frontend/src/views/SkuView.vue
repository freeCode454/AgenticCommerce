<script setup lang="ts">
import { ref, watch, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import client from '@/api/client'
import { useCollection } from '@/composables/useCollection'
import { useUiStore } from '@/stores/ui'
import { errorMessage, safeUrl } from '@/utils/format'
import type { Sku, ApiResponse } from '@/types'
import AppIcon from '@/components/ui/AppIcon.vue'
import PageHeading from '@/components/ui/PageHeading.vue'
import PageState from '@/components/ui/PageState.vue'
import AppDialog from '@/components/ui/AppDialog.vue'
import PaginationBar from '@/components/ui/PaginationBar.vue'
import MediaPreview from '@/components/ui/MediaPreview.vue'
import TaskCreateDialog from '@/components/ui/TaskCreateDialog.vue'
const route = useRoute(),
  router = useRouter(),
  ui = useUiStore(),
  list = useCollection<Sku>('/skus', 9)
const query = ref(''),
  category = ref(''),
  showForm = ref(false),
  editing = ref<Sku | null>(null),
  busy = ref(false),
  extracting = ref(false),
  formError = ref(''),
  creation = ref(false),
  chosen = ref<Sku>()
const form = ref({
    code: '',
    name: '',
    category: '户外运动',
    description: '',
    images: '',
  }),
  specs = ref<{ key: string; value: string }[]>([])
let debounce: ReturnType<typeof setTimeout> | undefined
watch(query, () => {
  clearTimeout(debounce)
  debounce = setTimeout(() => {
    list.params.q = query.value.trim() || undefined
    void list.reload(true)
  }, 300)
})
watch(category, () => {
  list.params.category = category.value || undefined
  void list.reload(true)
})
onUnmounted(() => clearTimeout(debounce))
function open(sku?: Sku) {
  editing.value = sku || null
  form.value = {
    code: sku?.code || '',
    name: sku?.name || '',
    category: sku?.category || '户外运动',
    description: sku?.description || '',
    images: (sku?.images || []).join('\n'),
  }
  specs.value = Object.entries(sku?.specs || {}).map(([key, value]) => ({
    key,
    value: String(value),
  }))
  formError.value = ''
  showForm.value = true
}
watch(
  () => route.query.new,
  (value) => {
    if (value === '1') {
      open()
      void router.replace('/skus')
    }
  },
  { immediate: true },
)
function generateCode() {
  form.value.code = 'SKU-' + crypto.randomUUID().slice(0, 8).toUpperCase()
}
function addTemplates() {
  const labels: Record<string, string[]> = {
    户外运动: ['材质', '重量', '尺寸'],
    数码配件: ['型号', '尺寸', '电池容量'],
    家居生活: ['材质', '尺寸', '容量'],
  }
  for (const key of labels[form.value.category] || ['材质', '尺寸'])
    if (!specs.value.some((row) => row.key === key)) specs.value.push({ key, value: '' })
}
async function extract() {
  if (extracting.value || busy.value) return
  if (!form.value.description.trim()) {
    formError.value = '先填写商品描述，再使用 AI 提取。'
    return
  }
  if (
    !(await ui.confirm(
      '使用 AI 提取规格',
      '将调用模型分析商品描述，可能产生费用。提取结果仍需你核对。',
      '提取规格',
    ))
  )
    return
  extracting.value = true
  formError.value = ''
  try {
    const response = await client.post<ApiResponse<Record<string, unknown>>>(
      '/skus/extract-specs',
      { description: form.value.description },
    )
    specs.value = Object.entries(response.data.data || {}).map(([key, value]) => ({
      key,
      value: String(value),
    }))
    ui.notify(
      specs.value.length ? '已提取规格，请核对后保存。' : '没有提取到明确规格，请手动填写。',
      specs.value.length ? 'success' : 'info',
    )
  } catch (cause) {
    formError.value = errorMessage(cause)
  } finally {
    extracting.value = false
  }
}
async function save() {
  if (busy.value || extracting.value) return
  formError.value = ''
  const values: Record<string, string> = {}
  for (const row of specs.value) {
    const key = row.key.trim(),
      value = row.value.trim()
    if (!key && !value) continue
    if (!key || !value) {
      formError.value = '请补全规格名称和数值，或删除空行。'
      return
    }
    if (key in values) {
      formError.value = '规格名称重复，请合并后保存。'
      return
    }
    values[key] = value
  }
  const images = form.value.images
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean)
  if (images.some((url) => !safeUrl(url))) {
    formError.value = '请填写有效的 HTTP 或 HTTPS 图片地址。'
    return
  }
  if (
    !editing.value &&
    !Object.keys(values).length &&
    form.value.description.trim() &&
    !(await ui.confirm(
      '保存并提取规格',
      '当前没有填写规格，保存时服务会调用 AI 提取，可能产生费用。你也可以取消并手动填写。',
      '保存并提取',
    ))
  )
    return
  busy.value = true
  try {
    const payload = {
      name: form.value.name.trim(),
      category: form.value.category,
      description: form.value.description,
      specs: values,
      images,
    }
    if (editing.value) await client.put(`/skus/${editing.value.id}`, payload)
    else await client.post('/skus', { ...payload, code: form.value.code.trim() })
    showForm.value = false
    ui.notify(editing.value ? '商品资料已更新' : '商品资料已保存')
    await list.reload(!editing.value)
  } catch (cause) {
    formError.value = errorMessage(cause, '保存失败，请检查商品编码。')
  } finally {
    busy.value = false
  }
}
async function remove(sku: Sku) {
  if (
    !(await ui.confirm(
      '删除商品资料',
      `将从商品列表中移除“${sku.name}”，已有任务记录会保留。`,
      '确认删除',
      true,
    ))
  )
    return
  try {
    await client.delete(`/skus/${sku.id}`)
    ui.notify('商品已移除')
    await list.reload(true)
  } catch (cause) {
    ui.notify(errorMessage(cause), 'error')
  }
}
function create(sku: Sku) {
  chosen.value = sku
  creation.value = true
}
</script>
<template>
  <PageHeading title="商品资料" description="每个好创意，都从真实的商品信息开始。">
    <button class="btn btn-primary" @click="open()">
      <AppIcon name="plus" :size="17" />
      录入新商品
    </button>
  </PageHeading>
  <div class="section-toolbar">
    <div class="filter-bar">
      <div class="search-input">
        <AppIcon name="search" :size="18" />
        <input
          v-model="query"
          type="search"
          placeholder="搜索名称或 SKU 编码"
          aria-label="搜索商品"
        />
      </div>
      <select v-model="category" class="select" aria-label="商品类目">
        <option value="">全部类目</option>
        <option>户外运动</option>
        <option>数码配件</option>
        <option>家居生活</option>
      </select>
    </div>
    <button class="btn btn-secondary btn-sm" :disabled="list.loading" @click="list.reload()">
      <AppIcon name="refresh" :size="16" />
      刷新
    </button>
  </div>
  <PageState
    :loading="list.loading"
    :error="list.error"
    :error-code="list.errorCode"
    :empty="!list.items.length"
    title="还没有相关商品"
    description="录入商品的名称、规格与参考图，为内容创作做好准备。"
    icon="box"
    @retry="list.reload()"
  >
    <template #action><button class="btn btn-primary" @click="open()">录入商品</button></template>
    <div class="products-grid">
      <article v-for="sku in list.items" :key="sku.id" class="product-card">
        <div class="product-cover">
          <MediaPreview :src="sku.images?.[0]" :alt="sku.name" />
          <span class="category-tag">{{ sku.category || '未分类' }}</span>
        </div>
        <div class="product-info">
          <span class="code-pill">{{ sku.code }}</span>
          <h2>{{ sku.name }}</h2>
          <p>{{ sku.description || '暂未填写商品描述' }}</p>
          <div class="product-specs">
            <span
              v-for="(value, key) in Object.fromEntries(
                Object.entries(sku.specs || {}).slice(0, 3),
              )"
              :key="key"
            >
              {{ key }}：{{ value }}
            </span>
            <span v-if="!Object.keys(sku.specs || {}).length">待补充商品规格</span>
          </div>
          <div class="product-actions">
            <button class="btn btn-primary btn-sm" @click="create(sku)">
              <AppIcon name="spark" :size="16" />
              为这个商品创作
            </button>
            <button
              class="icon-button"
              :aria-label="`编辑${sku.name}`"
              title="编辑商品"
              @click="open(sku)"
            >
              <AppIcon name="edit" :size="17" />
            </button>
            <button
              class="icon-button"
              :aria-label="`删除${sku.name}`"
              title="删除商品"
              @click="remove(sku)"
            >
              <AppIcon name="trash" :size="17" />
            </button>
          </div>
        </div>
      </article>
    </div>
    <PaginationBar
      :page="list.page"
      :size="list.size"
      :total="list.total"
      :loading="list.loading"
      @change="list.page = $event"
    />
  </PageState>
  <AppDialog
    v-model="showForm"
    :title="editing ? '编辑商品资料' : '录入新商品'"
    description="准确的规格和参考图，能让创作更贴近实际商品。"
    :busy="busy || extracting"
    wide
  >
    <form id="sku-form" @submit.prevent="save">
      <div class="form-grid">
        <div class="field">
          <label for="sku-code">商品编码</label>
          <div class="row">
            <input
              id="sku-code"
              v-model="form.code"
              required
              maxlength="128"
              class="input"
              placeholder="例如 OUT-2026-001"
              :disabled="!!editing || busy"
            />
            <button
              v-if="!editing"
              type="button"
              class="btn btn-secondary btn-sm"
              @click="generateCode"
            >
              生成
            </button>
          </div>
        </div>
        <div class="field">
          <label for="sku-category">商品类目</label>
          <select id="sku-category" v-model="form.category" class="select" :disabled="busy">
            <option>户外运动</option>
            <option>数码配件</option>
            <option>家居生活</option>
          </select>
        </div>
      </div>
      <div class="field">
        <label for="sku-name">商品名称</label>
        <input
          id="sku-name"
          v-model="form.name"
          required
          class="input"
          maxlength="256"
          placeholder="填写实际商品名称"
          :disabled="busy"
        />
      </div>
      <div class="field">
        <div class="hint-label">
          <label for="sku-description">商品描述</label>
          <button class="text-button" type="button" :disabled="extracting || busy" @click="extract">
            <span v-if="extracting" class="spinner" />
            <AppIcon v-else name="spark" :size="16" />
            {{ extracting ? '正在提取…' : 'AI 提取规格' }}
          </button>
        </div>
        <textarea
          id="sku-description"
          v-model="form.description"
          class="textarea"
          placeholder="描述材质、尺寸、功能和实际卖点。"
          :disabled="busy || extracting"
        />
      </div>
      <div class="form-section">
        <div class="hint-label">
          <label>商品规格</label>
          <button type="button" class="text-button" @click="addTemplates">添加类目空白字段</button>
        </div>
        <p>只填写已确认的真实参数，不填示例或推测数值。</p>
        <div v-for="(spec, index) in specs" :key="index" class="spec-row">
          <input
            v-model="spec.key"
            class="input"
            placeholder="规格名称"
            :aria-label="`规格名称 ${index + 1}`"
            :disabled="busy || extracting"
          />
          <input
            v-model="spec.value"
            class="input"
            placeholder="真实数值"
            :aria-label="`规格数值 ${index + 1}`"
            :disabled="busy || extracting"
          />
          <button
            class="icon-button"
            type="button"
            :aria-label="`删除规格 ${index + 1}`"
            :disabled="busy || extracting"
            @click="specs.splice(index, 1)"
          >
            <AppIcon name="close" :size="16" />
          </button>
        </div>
        <button
          class="text-button spaced"
          type="button"
          :disabled="busy || extracting"
          @click="specs.push({ key: '', value: '' })"
        >
          <AppIcon name="plus" :size="15" />
          添加规格
        </button>
      </div>
      <div class="field">
        <label for="sku-images">参考图片地址（可选）</label>
        <textarea
          id="sku-images"
          v-model="form.images"
          class="textarea"
          placeholder="每行一个图片 URL，没有参考图时可留空。"
          :disabled="busy"
        />
        <small class="field-help">不会为你的商品自动填入其他产品的示例图片。</small>
      </div>
      <p class="cost-note">
        <AppIcon name="info" :size="16" />
        AI 提取可能产生费用。创建商品时若有描述但未填规格，保存也会触发提取。
      </p>
      <p v-if="formError" class="form-error" role="alert">{{ formError }}</p>
    </form>
    <template #footer>
      <button class="btn btn-secondary" :disabled="busy || extracting" @click="showForm = false">
        取消
      </button>
      <button class="btn btn-primary" type="submit" form="sku-form" :disabled="busy || extracting">
        <span v-if="busy" class="spinner" />
        {{ busy ? '正在保存…' : '保存商品' }}
      </button>
    </template>
  </AppDialog>
  <TaskCreateDialog
    v-if="creation"
    v-model="creation"
    :sku="chosen"
    @created="router.push(`/workbench/${$event}`)"
  />
</template>
