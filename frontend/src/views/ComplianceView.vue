<script setup lang="ts">
import { ref } from 'vue'
import client from '@/api/client'
import { useCollection } from '@/composables/useCollection'
import { dateText, errorMessage } from '@/utils/format'
import type { ApiResponse, Report } from '@/types'
import PageHeading from '@/components/ui/PageHeading.vue'
import PageState from '@/components/ui/PageState.vue'
import PaginationBar from '@/components/ui/PaginationBar.vue'
import AppDialog from '@/components/ui/AppDialog.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import ReviewResult from '@/components/ui/ReviewResult.vue'
const list = useCollection<Report>('/compliance/reports', 12),
  open = ref(false),
  checking = ref(false),
  busy = ref(false),
  loading = ref(false),
  failure = ref(''),
  selected = ref<Report | null>(null),
  title = ref(''),
  content = ref('')
let request = 0
async function view(report: Report) {
  if (!report.id) return
  const seq = ++request
  selected.value = report
  open.value = true
  loading.value = true
  failure.value = ''
  try {
    const { data } = await client.get<ApiResponse<Report>>(`/compliance/reports/${report.id}`)
    if (seq === request) selected.value = data.data
  } catch (e) {
    if (seq === request) failure.value = errorMessage(e)
  } finally {
    if (seq === request) loading.value = false
  }
}
function start() {
  title.value = ''
  content.value = ''
  failure.value = ''
  checking.value = true
}
async function check() {
  if (busy.value) return
  busy.value = true
  failure.value = ''
  try {
    const { data } = await client.post<ApiResponse<Report>>('/compliance/check', {
      title: title.value.trim(),
      content: content.value.trim(),
      target_platform: 'amazon',
    })
    selected.value = data.data
    checking.value = false
    open.value = true
    await list.reload(true)
  } catch (e) {
    failure.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <PageHeading
    title="审核中心"
    description="把好内容发布前的每一道关，查看质量与合规建议。"
    eyebrow="QUALITY & COMPLIANCE"
  >
    <button class="btn btn-primary" @click="start">
      <AppIcon name="shield" :size="17" />
      检查一段文案
    </button>
  </PageHeading>
  <div class="notice mb-5">
    <AppIcon name="info" :size="17" />
    <span>审核报告为模型辅助建议。编辑文案后，旧报告会标记失效，需要重新审核。</span>
  </div>
  <PageState
    :loading="list.loading"
    :error="list.error"
    :error-code="list.errorCode"
    :empty="!list.items.length"
    title="暂无审核报告"
    description="生成任务完成审核，或主动检查文案后，可在此查看结果。"
    icon="shield"
    @retry="list.reload()"
  >
    <div class="panel table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>商品 / 任务</th>
            <th>综合评分</th>
            <th>审核结果</th>
            <th>审核时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="report in list.items" :key="report.id">
            <td>
              <strong>{{ report.sku_name || report.sku_code || '独立文案检查' }}</strong>
              <small>{{ report.task_id || report.id }}</small>
            </td>
            <td>
              <span class="score-value">{{ report.score }}</span>
              <span class="text-muted text-sm">/ 100</span>
            </td>
            <td>
              <StatusBadge
                :status="
                  report.status === 'outdated' ? 'outdated' : report.passed ? 'passed' : 'rejected'
                "
              />
            </td>
            <td>{{ dateText(report.create_time) }}</td>
            <td>
              <button class="text-button" @click="view(report)">
                查看详情
                <AppIcon name="arrow-right" :size="14" />
              </button>
            </td>
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
  <AppDialog v-model="open" title="审核详情" drawer>
    <PageState :loading="loading" :error="failure" @retry="selected && view(selected)">
      <ReviewResult v-if="selected" :report="selected" />
      <RouterLink
        v-if="selected?.task_id"
        class="btn btn-secondary mt-5"
        :to="`/workbench/${selected.task_id}`"
        @click="open = false"
      >
        打开关联工作台
      </RouterLink>
    </PageState>
  </AppDialog>
  <AppDialog
    v-model="checking"
    title="检查文案"
    description="使用当前服务端模型进行质量与合规检查。"
    :busy="busy"
  >
    <form id="compliance-check" class="form-stack" @submit.prevent="check">
      <p class="notice notice-warning">
        点击“开始检查”会调用 AI 模型，可能产生费用。当前目标平台为 Amazon。
      </p>
      <p v-if="failure" class="notice notice-error" role="alert">
        {{ failure }}
      </p>
      <div class="form-group">
        <label for="review-title">商品标题</label>
        <input id="review-title" v-model="title" class="form-input" required :disabled="busy" />
      </div>
      <div class="form-group">
        <label for="review-content">待审核文案</label>
        <textarea
          id="review-content"
          v-model="content"
          class="form-textarea"
          rows="8"
          required
          :disabled="busy"
        />
      </div>
    </form>
    <template #footer>
      <button class="btn btn-secondary" :disabled="busy" @click="checking = false">取消</button>
      <button class="btn btn-primary" type="submit" form="compliance-check" :disabled="busy">
        {{ busy ? '正在检查…' : '开始检查（可能产生费用）' }}
      </button>
    </template>
  </AppDialog>
</template>
