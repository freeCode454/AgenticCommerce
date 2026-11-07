<script setup lang="ts">
import { ref } from 'vue'
import client from '@/api/client'
import { createSubmissionKey } from '@/utils/submissionKey'
import { useCollection } from '@/composables/useCollection'
import { useUiStore } from '@/stores/ui'
import { dateText, errorMessage } from '@/utils/format'
import type { Batch, Sku, Task, ApiResponse } from '@/types'
import AppIcon from '@/components/ui/AppIcon.vue'
import PageHeading from '@/components/ui/PageHeading.vue'
import PageState from '@/components/ui/PageState.vue'
import PaginationBar from '@/components/ui/PaginationBar.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import AppDialog from '@/components/ui/AppDialog.vue'
import SkuPicker from '@/components/ui/SkuPicker.vue'
const list = useCollection<Batch>('/batches', 9),
  ui = useUiStore(),
  show = ref(false),
  name = ref(''),
  selected = ref<Sku[]>([]),
  busy = ref(false),
  error = ref('')
const detailOpen = ref(false),
  detail = ref<{ batch: Batch; tasks: Task[] } | null>(null),
  detailLoading = ref(false),
  detailError = ref(''),
  detailId = ref('')
const submissionKey = createSubmissionKey()
let detailSequence = 0
function open() {
  submissionKey.reset()
  name.value = ''
  selected.value = []
  error.value = ''
  show.value = true
}
async function submit() {
  if (busy.value) return
  if (!name.value.trim() || !selected.value.length) {
    error.value = '请填写批次名称并选择商品。'
    return
  }
  busy.value = true
  error.value = ''
  try {
    const payload = {
      name: name.value.trim(),
      sku_ids: selected.value.map((sku) => sku.id),
      config: {
        language: 'en',
        platform: 'amazon',
        media_type: 'both',
        max_retries: 2,
      },
    }
    const response = await client.post<ApiResponse<{ batch_id: string }>>('/batches', payload, {
      headers: { 'Idempotency-Key': submissionKey.forPayload(payload) },
    })
    submissionKey.reset()
    show.value = false
    ui.notify('批次已创建')
    void list.reload(true)
    void loadDetail(response.data.data.batch_id)
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    busy.value = false
  }
}
async function loadDetail(id: string) {
  const seq = ++detailSequence
  detailId.value = id
  detailOpen.value = true
  detailLoading.value = true
  detailError.value = ''
  try {
    const response = await client.get<ApiResponse<{ batch: Batch; tasks: Task[] }>>(
      `/batches/${id}`,
    )
    if (seq === detailSequence) detail.value = response.data.data
  } catch (cause) {
    if (seq === detailSequence) detailError.value = errorMessage(cause)
  } finally {
    if (seq === detailSequence) detailLoading.value = false
  }
}
</script>
<template>
  <PageHeading title="批量任务" description="为一组商品安排完整内容创作，集中查看各任务进展。">
    <button class="btn btn-primary" @click="open">
      <AppIcon name="plus" :size="17" />
      新建批次
    </button>
  </PageHeading>
  <div class="section-toolbar">
    <span class="subtle">按创建时间排列 · 每批最多 100 件商品</span>
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
    title="还没有批量任务"
    description="为多件商品安排创作，也能保持井然有序。"
    icon="grid"
    @retry="list.reload()"
  >
    <template #action>
      <button class="btn btn-primary" @click="open">创建第一个批次</button>
    </template>
    <div class="three-grid">
      <article v-for="batch in list.items" :key="batch.id" class="card batch-card">
        <div class="row between">
          <span class="provider-mark"><AppIcon name="grid" /></span>
          <StatusBadge :status="batch.status" />
        </div>
        <h2>{{ batch.name }}</h2>
        <p class="card-description">{{ batch.total_count }} 件商品 · 完整内容生成</p>
        <p class="subtle spaced">各任务的实际进展，请在批次详情查看。</p>
        <div class="row between spaced wrap">
          <span class="subtle">{{ dateText(batch.create_time) }}</span>
          <button class="text-button" @click="loadDetail(batch.id)">
            查看详情
            <AppIcon name="arrow-right" :size="15" />
          </button>
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
    v-model="show"
    title="创建批量任务"
    description="选择需要创作的真实商品，最多 100 件。"
    :busy="busy"
    wide
  >
    <form id="batch-form" @submit.prevent="submit">
      <div class="field">
        <label for="batch-name">批次名称</label>
        <input
          id="batch-name"
          v-model="name"
          class="input"
          required
          maxlength="128"
          placeholder="例如：秋季新品内容创作"
          :disabled="busy"
        />
      </div>
      <div class="field">
        <span class="field-label">选择商品 · 已选 {{ selected.length }} / 100</span>
        <SkuPicker v-if="show" v-model="selected" multiple />
      </div>
      <div class="notice">
        <AppIcon name="layers" />
        <span>每件商品生成英文 Amazon 文案、图片与视频；审核未通过时最多重试 2 次。</span>
      </div>
      <p class="cost-note">
        <AppIcon name="info" :size="16" />
        创建批次会为所选商品调用模型，可能产生多笔生成费用。
      </p>
      <p v-if="error" class="form-error" role="alert">{{ error }}</p>
    </form>
    <template #footer>
      <button class="btn btn-secondary" :disabled="busy" @click="show = false">取消</button>
      <button
        class="btn btn-primary"
        form="batch-form"
        type="submit"
        :disabled="busy || !selected.length || !name.trim()"
      >
        <span v-if="busy" class="spinner" />
        {{ busy ? '正在创建…' : `创建批次（${selected.length} 件）` }}
      </button>
    </template>
  </AppDialog>
  <AppDialog v-model="detailOpen" :title="detail?.batch.name || '批次详情'" drawer>
    <PageState
      :loading="detailLoading"
      :error="detailError"
      :empty="!detail"
      @retry="loadDetail(detailId)"
    >
      <template v-if="detail">
        <div class="batch-counts">
          <div>
            <span>任务总数</span>
            <b>{{ detail.tasks.length }}</b>
          </div>
          <div>
            <span>已完成</span>
            <b>{{ detail.tasks.filter((task) => task.status === 'completed').length }}</b>
          </div>
          <div>
            <span>失败</span>
            <b>{{ detail.tasks.filter((task) => task.status === 'failed').length }}</b>
          </div>
          <div>
            <span>已取消</span>
            <b>{{ detail.tasks.filter((task) => task.status === 'canceled').length }}</b>
          </div>
        </div>
        <div v-for="task in detail.tasks" :key="task.id" class="file-row">
          <AppIcon name="layers" />
          <span>
            <span class="code-pill">{{ task.id }}</span>
            <p class="subtle">商品：{{ task.sku_id }}</p>
          </span>
          <StatusBadge :status="task.status" />
          <RouterLink :to="`/workbench/${task.id}`" class="text-button" @click="detailOpen = false">
            打开任务
          </RouterLink>
        </div>
      </template>
    </PageState>
  </AppDialog>
</template>
