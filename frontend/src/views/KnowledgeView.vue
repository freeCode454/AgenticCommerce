<script setup lang="ts">
import { reactive, ref } from 'vue'
import client from '@/api/client'
import { useCollection } from '@/composables/useCollection'
import { useUiStore } from '@/stores/ui'
import { dateText, errorMessage } from '@/utils/format'
import type { ApiResponse, KnowledgeDoc, KnowledgeDetail } from '@/types'
import PageHeading from '@/components/ui/PageHeading.vue'
import PageState from '@/components/ui/PageState.vue'
import PaginationBar from '@/components/ui/PaginationBar.vue'
import AppDialog from '@/components/ui/AppDialog.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
const ui = useUiStore(),
  list = useCollection<KnowledgeDoc>('/knowledge/docs', 10, { category: '' }),
  open = ref(false),
  drawer = ref(false),
  busy = ref(false),
  failure = ref(''),
  docLoading = ref(false),
  docError = ref(''),
  selected = ref<KnowledgeDetail | null>(null),
  selectedId = ref('')
const form = reactive({
    category: 'brand',
    doc_type: 'brand',
    name: '',
    content: '',
  }),
  query = ref(''),
  searching = ref(false),
  searched = ref(false),
  searchError = ref(''),
  results = ref<{ id: string; content: string; doc_type: string }[]>([])
const categories: Record<string, string> = {
  brand: '品牌规范',
  compliance: '合规政策',
  market: '市场洞察',
}
let sequence = 0
function start() {
  Object.assign(form, {
    category: 'brand',
    doc_type: 'brand',
    name: '',
    content: '',
  })
  failure.value = ''
  open.value = true
}
async function submit() {
  if (busy.value) return
  busy.value = true
  failure.value = ''
  try {
    await client.post('/knowledge/docs', {
      ...form,
      doc_type: form.category,
      name: form.name.trim(),
      content: form.content.trim(),
    })
    open.value = false
    ui.notify('文档已录入，请以文档列表显示的索引状态为准。')
    await list.reload(true)
  } catch (e) {
    failure.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
async function view(id: string) {
  const seq = ++sequence
  selectedId.value = id
  selected.value = null
  drawer.value = true
  docLoading.value = true
  docError.value = ''
  try {
    const { data } = await client.get<ApiResponse<KnowledgeDetail>>(`/knowledge/docs/${id}`)
    if (seq === sequence) selected.value = data.data
  } catch (e) {
    if (seq === sequence) docError.value = errorMessage(e)
  } finally {
    if (seq === sequence) docLoading.value = false
  }
}
async function search() {
  if (searching.value || !query.value.trim()) return
  searching.value = true
  searched.value = false
  searchError.value = ''
  results.value = []
  try {
    const { data } = await client.post<
      ApiResponse<{
        results: { id: string; content: string; doc_type: string }[]
      }>
    >('/knowledge/query', { query_text: query.value.trim(), top_k: 3 })
    results.value = data.data.results
    searched.value = true
  } catch (e) {
    searchError.value = errorMessage(e)
  } finally {
    searching.value = false
  }
}
</script>
<template>
  <PageHeading
    title="品牌知识库"
    description="沉淀品牌规范、合规政策和市场洞察，为创作提供依据。"
    eyebrow="BRAND KNOWLEDGE"
  >
    <button class="btn btn-primary" @click="start">
      <AppIcon name="plus" :size="17" />
      录入知识文档
    </button>
  </PageHeading>
  <div class="knowledge-layout">
    <section class="stack">
      <div class="toolbar">
        <div class="filter-group">
          <label for="doc-category">文档分类</label>
          <select
            id="doc-category"
            v-model="list.params.category"
            class="form-select"
            @change="list.reload(true)"
          >
            <option value="">全部分类</option>
            <option v-for="(name, key) in categories" :key="key" :value="key">
              {{ name }}
            </option>
          </select>
        </div>
        <button
          class="icon-button"
          aria-label="刷新文档"
          :disabled="list.loading"
          @click="list.reload()"
        >
          <AppIcon name="refresh" :size="18" />
        </button>
      </div>
      <PageState
        :loading="list.loading"
        :error="list.error"
        :error-code="list.errorCode"
        :empty="!list.items.length"
        title="知识库等待第一份积累"
        description="粘贴文档正文，建立品牌专属的创作依据。"
        icon="book"
        @retry="list.reload()"
      >
        <div class="panel table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>文档名称</th>
                <th>分类</th>
                <th>索引状态</th>
                <th>录入时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="doc in list.items" :key="doc.id">
                <td>
                  <button class="table-title" @click="view(doc.id)">
                    {{ doc.name }}
                  </button>
                  <small>{{ doc.id }}</small>
                </td>
                <td>{{ categories[doc.category] || doc.category }}</td>
                <td><StatusBadge :status="doc.vector_status" /></td>
                <td>{{ dateText(doc.create_time) }}</td>
              </tr>
            </tbody>
          </table>
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
    </section>
    <aside class="card knowledge-search">
      <span class="empty-icon"><AppIcon name="search" :size="24" /></span>
      <h2 class="content-title mt-4">寻找品牌的答案</h2>
      <p class="text-muted mt-2">输入一个问题，检索相关知识片段。</p>
      <form class="form-stack mt-5" @submit.prevent="search">
        <label class="sr-only" for="knowledge-query">知识检索问题</label>
        <textarea
          id="knowledge-query"
          v-model="query"
          class="form-textarea"
          placeholder="输入需要查找的品牌规范或政策"
          rows="4"
          required
          :disabled="searching"
        />
        <p class="field-hint">主动检索会调用向量模型，可能产生费用。</p>
        <button class="btn btn-primary btn-full" :disabled="searching || !query.trim()">
          <AppIcon name="search" :size="16" />
          {{ searching ? '正在检索…' : '开始检索' }}
        </button>
      </form>
      <p v-if="searchError" class="notice notice-error mt-4" role="alert">
        {{ searchError }}
      </p>
      <p v-if="searched && !results.length" class="notice mt-4">未检索到相关知识片段。</p>
      <article v-for="(result, i) in results" :key="result.id" class="recall-result">
        <span class="badge badge-neutral">
          片段 {{ i + 1 }} · {{ categories[result.doc_type] || result.doc_type }}
        </span>
        <p class="prose mt-3">{{ result.content }}</p>
      </article>
    </aside>
  </div>
  <AppDialog v-model="open" title="录入知识文档" :busy="busy">
    <form id="knowledge-create" class="form-stack" @submit.prevent="submit">
      <p class="notice notice-warning">
        提交将调用向量模型保存索引，可能产生费用。当前支持粘贴正文录入。
      </p>
      <p v-if="failure" class="notice notice-error" role="alert">
        {{ failure }}
      </p>
      <div class="form-group">
        <label for="knowledge-category">文档分类</label>
        <select
          id="knowledge-category"
          v-model="form.category"
          class="form-select"
          :disabled="busy"
        >
          <option v-for="(name, key) in categories" :key="key" :value="key">
            {{ name }}
          </option>
        </select>
      </div>
      <div class="form-group">
        <label for="knowledge-name">文档名称</label>
        <input
          id="knowledge-name"
          v-model="form.name"
          class="form-input"
          maxlength="256"
          required
          :disabled="busy"
        />
      </div>
      <div class="form-group">
        <label for="knowledge-content">正文内容</label>
        <textarea
          id="knowledge-content"
          v-model="form.content"
          class="form-textarea"
          rows="9"
          required
          :disabled="busy"
        />
      </div>
    </form>
    <template #footer>
      <button class="btn btn-secondary" :disabled="busy" @click="open = false">取消</button>
      <button type="submit" form="knowledge-create" class="btn btn-primary" :disabled="busy">
        {{ busy ? '正在建立索引…' : '录入并向量化' }}
      </button>
    </template>
  </AppDialog>
  <AppDialog v-model="drawer" title="知识文档详情" drawer>
    <PageState :loading="docLoading" :error="docError" @retry="view(selectedId)">
      <template v-if="selected">
        <h2 class="content-title">{{ selected.name }}</h2>
        <div class="row wrap mt-3">
          <span class="badge badge-neutral">
            {{ categories[selected.category] || selected.category }}
          </span>
          <StatusBadge :status="selected.vector_status" />
        </div>
        <article v-for="chunk in selected.chunks" :key="chunk.id" class="mt-5">
          <p class="text-muted text-sm">文档片段 {{ chunk.index }}</p>
          <p class="prose mt-3">{{ chunk.content }}</p>
        </article>
        <p v-if="!selected.chunks.length" class="notice mt-5">该文档暂无正文片段。</p>
      </template>
    </PageState>
  </AppDialog>
</template>
