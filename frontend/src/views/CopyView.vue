<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import client from '@/api/client'
import { useCollection } from '@/composables/useCollection'
import { useUiStore } from '@/stores/ui'
import { dateText, errorMessage, fullCopy } from '@/utils/format'
import type { ApiResponse, CopyContent } from '@/types'
import PageHeading from '@/components/ui/PageHeading.vue'
import PageState from '@/components/ui/PageState.vue'
import PaginationBar from '@/components/ui/PaginationBar.vue'
import AppDialog from '@/components/ui/AppDialog.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
const route = useRoute(),
  ui = useUiStore(),
  list = useCollection<CopyContent>('/copies', 8, {
    task_id: String(route.query.task_id || ''),
  }),
  open = ref(false),
  editing = ref(false),
  selected = ref<CopyContent | null>(null),
  busy = ref(false),
  fetching = ref(false),
  failure = ref(''),
  loadError = ref('')
const form = reactive({
  title: '',
  bullets: '',
  description: '',
  keywords: '',
})
let request = 0
watch(
  () => route.query.task_id,
  (value) => {
    list.params.task_id = String(value || '')
    void list.reload(true)
  },
)
async function view(copy: CopyContent, edit = false) {
  if (!copy.id) return
  const seq = ++request
  selected.value = copy
  editing.value = edit
  open.value = true
  fetching.value = true
  failure.value = ''
  loadError.value = ''
  try {
    const { data } = await client.get<ApiResponse<CopyContent>>(`/copies/${copy.id}`)
    if (seq !== request || !open.value) return
    selected.value = data.data
    fill()
  } catch (e) {
    if (seq === request) loadError.value = errorMessage(e)
  } finally {
    if (seq === request) fetching.value = false
  }
}
function editSelected() {
  editing.value = true
  fill()
}
function fill() {
  if (!selected.value) return
  Object.assign(form, {
    title: selected.value.title,
    bullets: (selected.value.bullets || []).join('\n'),
    description: selected.value.description || '',
    keywords: (selected.value.keywords || []).join(', '),
  })
}
async function save() {
  if (busy.value || !selected.value?.id) return
  busy.value = true
  failure.value = ''
  try {
    await client.put(`/copies/${selected.value.id}`, {
      title: form.title.trim(),
      bullets: form.bullets
        .split('\n')
        .map((v) => v.trim())
        .filter(Boolean),
      description: form.description.trim(),
      keywords: form.keywords
        .split(/[,，\n]/)
        .map((v) => v.trim())
        .filter(Boolean),
    })
    open.value = false
    ui.notify('文案已保存，需要重新审核后才能交付。')
    await list.reload()
  } catch (e) {
    failure.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
watch(open, (value) => {
  if (!value) {
    ++request
    selected.value = null
    failure.value = ''
  }
})
</script>
<template>
  <PageHeading
    title="文案内容"
    description="让产品价值被清楚地看见，管理每一份品牌表达。"
    eyebrow="COPYWRITING"
  />
  <div class="toolbar">
    <span class="text-muted">当前生成内容为英文 Amazon 商品文案</span>
    <RouterLink v-if="list.params.task_id" class="text-button" to="/copies">
      查看全部文案
    </RouterLink>
    <button class="btn btn-secondary" :disabled="list.loading" @click="list.reload()">
      <AppIcon name="refresh" :size="16" />
      刷新
    </button>
  </div>
  <PageState
    :loading="list.loading"
    :error="list.error"
    :error-code="list.errorCode"
    :empty="!list.items.length"
    title="还没有文案内容"
    description="生成任务产出文案后，会自动汇集到这里。"
    icon="file"
    @retry="list.reload()"
  >
    <div class="copy-list">
      <article v-for="copy in list.items" :key="copy.id" class="copy-card">
        <div class="copy-meta">
          <span>
            {{ copy.sku_name || copy.sku_code || '商品文案' }} · {{ dateText(copy.create_time) }}
          </span>
          <StatusBadge :status="copy.status || 'draft'" />
        </div>
        <h2>{{ copy.title }}</h2>
        <p class="prose">{{ copy.description || '暂无商品描述' }}</p>
        <div class="copy-card-footer">
          <span class="text-muted text-sm">
            {{ copy.bullets?.length || 0 }} 条卖点 · {{ copy.language || '未标注语言' }}
          </span>
          <div class="row wrap">
            <button class="btn btn-secondary btn-sm" @click="ui.copy(fullCopy(copy))">
              <AppIcon name="copy" :size="14" />
              复制
            </button>
            <button class="btn btn-secondary btn-sm" @click="view(copy)">查看全文</button>
            <button class="btn btn-primary btn-sm" @click="view(copy, true)">
              <AppIcon name="edit" :size="14" />
              编辑
            </button>
          </div>
        </div>
      </article>
    </div>
  </PageState>
  <PaginationBar
    :page="list.page"
    @change="list.page = $event"
    :total="list.total"
    :size="list.size"
    :loading="list.loading"
    :has-more="list.hasMore"
  />
  <AppDialog v-model="open" :title="editing ? '编辑文案' : '文案详情'" :busy="busy" wide>
    <PageState :loading="fetching" :error="loadError" @retry="selected && view(selected, editing)">
      <form v-if="editing" id="copy-edit" class="form-stack" @submit.prevent="save">
        <p class="notice notice-warning">
          保存会使原审核结果失效，需要重新审核。重新运行任务可能产生模型费用。
        </p>
        <p v-if="failure" class="notice notice-error" role="alert">
          {{ failure }}
        </p>
        <div class="form-group">
          <label for="copy-title">商品标题</label>
          <textarea
            id="copy-title"
            v-model="form.title"
            class="form-textarea"
            rows="3"
            required
            :disabled="busy"
          />
        </div>
        <div class="form-group">
          <label for="copy-bullets">核心卖点 · 每行一条</label>
          <textarea
            id="copy-bullets"
            v-model="form.bullets"
            class="form-textarea"
            rows="6"
            :disabled="busy"
          />
        </div>
        <div class="form-group">
          <label for="copy-description">商品描述</label>
          <textarea
            id="copy-description"
            v-model="form.description"
            class="form-textarea"
            rows="6"
            :disabled="busy"
          />
        </div>
        <div class="form-group">
          <label for="copy-keywords">关键词 · 逗号分隔</label>
          <textarea
            id="copy-keywords"
            v-model="form.keywords"
            class="form-textarea"
            rows="2"
            :disabled="busy"
          />
        </div>
      </form>
      <div v-else-if="selected" class="stack">
        <h2 class="content-title">{{ selected.title }}</h2>
        <ul class="bullets">
          <li v-for="(bullet, i) in selected.bullets" :key="i">{{ bullet }}</li>
        </ul>
        <p class="prose">{{ selected.description }}</p>
        <div class="row wrap">
          <span v-for="(keyword, i) in selected.keywords" :key="i" class="badge badge-neutral">
            {{ keyword }}
          </span>
        </div>
      </div>
    </PageState>
    <template #footer>
      <button class="btn btn-secondary" :disabled="busy" @click="open = false">关闭</button>
      <template v-if="!fetching && !loadError && selected">
        <button v-if="!editing" class="btn btn-secondary" @click="ui.copy(fullCopy(selected))">
          复制全文
        </button>
        <button v-if="!editing" class="btn btn-primary" @click="editSelected">编辑文案</button>
        <button v-else type="submit" form="copy-edit" class="btn btn-primary" :disabled="busy">
          {{ busy ? '保存中…' : '保存并标记待审核' }}
        </button>
      </template>
      <button
        v-else-if="editing && !fetching && !loadError"
        type="submit"
        form="copy-edit"
        class="btn btn-primary"
        :disabled="busy"
      >
        {{ busy ? '保存中…' : '重试保存' }}
      </button>
    </template>
  </AppDialog>
</template>
