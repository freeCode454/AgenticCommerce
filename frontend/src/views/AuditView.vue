<script setup lang="ts">
import { ref } from 'vue'
import { useResource } from '@/composables/useResource'
import { useCollection } from '@/composables/useCollection'
import { dateText, moneyText, numberText, outputText } from '@/utils/format'
import type { CostSummary, OperationLog } from '@/types'
import PageHeading from '@/components/ui/PageHeading.vue'
import PageState from '@/components/ui/PageState.vue'
import PaginationBar from '@/components/ui/PaginationBar.vue'
import AppDialog from '@/components/ui/AppDialog.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
const { data: cost, loading, error, errorCode, reload } = useResource<CostSummary>('/audit/costs'),
  list = useCollection<OperationLog>('/audit/logs', 10, { action: '' }),
  selected = ref<OperationLog | null>(null),
  open = ref(false)
function refresh() {
  void reload()
  void list.reload()
}
function viewRecord(record: OperationLog) {
  selected.value = record
  open.value = true
}
</script>
<template>
  <PageHeading
    title="用量与费用"
    description="从真实执行记录，了解工作空间的模型用量。"
    eyebrow="USAGE & COST"
  >
    <button class="btn btn-secondary" :disabled="loading || list.loading" @click="refresh">
      <AppIcon name="refresh" :size="16" />
      刷新数据
    </button>
  </PageHeading>
  <PageState :loading="loading" :error="error" :error-code="errorCode" @retry="reload()">
    <div class="metrics-grid">
      <article class="metric metric-cost">
        <div class="metric-top">
          预估费用 · USD
          <AppIcon name="chart" :size="18" />
        </div>
        <div class="metric-number">{{ moneyText(cost?.total_cost_usd) }}</div>
        <p>任务节点累计记录的费用估算</p>
      </article>
      <article class="metric">
        <div class="metric-top">
          节点执行记录
          <AppIcon name="layers" :size="18" />
        </div>
        <div class="metric-number">{{ numberText(cost?.total_runs) }}</div>
        <p>包含重试产生的执行记录</p>
      </article>
      <article class="metric">
        <div class="metric-top">
          输入 Tokens
          <AppIcon name="arrow-right" :size="18" />
        </div>
        <div class="metric-number">
          {{ numberText(cost?.total_prompt_tokens) }}
        </div>
        <p>模型记录的输入用量</p>
      </article>
      <article class="metric">
        <div class="metric-top">
          输出 Tokens
          <AppIcon name="file" :size="18" />
        </div>
        <div class="metric-number">
          {{ numberText(cost?.total_completion_tokens) }}
        </div>
        <p>累计 Tokens {{ numberText(cost?.total_tokens) }}</p>
      </article>
    </div>
  </PageState>
  <div class="notice mb-5">
    <AppIcon name="info" :size="18" />
    <span>费用为执行记录的预估汇总，最终账单以模型服务商为准。当前尚无可靠的分模型费用明细。</span>
  </div>
  <div v-if="cost?.unreported_video_jobs" class="notice notice-warning mb-5">
    <AppIcon name="info" :size="18" />
    <span>
      {{
        cost.unreported_video_jobs
      }}
      个视频任务尚无可靠费用数据，费用合计未包含这些任务，请以厂商账单为准。
    </span>
  </div>
  <div class="section-heading">
    <div>
      <h2>操作记录</h2>
      <p>查看当前工作空间中的业务操作。</p>
    </div>
  </div>
  <form class="toolbar" @submit.prevent="list.reload(true)">
    <div class="filter-group">
      <label for="audit-action">操作类型</label>
      <input
        id="audit-action"
        v-model="list.params.action"
        class="form-input"
        placeholder="输入完整操作类型，如 create_task"
      />
    </div>
    <button class="btn btn-secondary" :disabled="list.loading">应用筛选</button>
  </form>
  <PageState
    :loading="list.loading"
    :error="list.error"
    :error-code="list.errorCode"
    :empty="!list.items.length"
    title="暂无操作记录"
    description="当前工作空间的业务操作记录会显示在这里。"
    icon="file"
    @retry="list.reload()"
  >
    <div class="panel table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>操作人</th>
            <th>操作</th>
            <th>对象</th>
            <th>时间</th>
            <th>详情</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="log in list.items" :key="log.id">
            <td>{{ log.user_name || log.user_id || '未记录' }}</td>
            <td>
              <span class="code-pill">{{ log.action }}</span>
            </td>
            <td>
              {{ log.target_type || '—' }}
              <small>{{ log.target_id }}</small>
            </td>
            <td>{{ dateText(log.create_time) }}</td>
            <td>
              <button class="text-button" @click="viewRecord(log)">
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
  <AppDialog v-model="open" title="操作详情" drawer>
    <template v-if="selected">
      <dl class="details-list">
        <div>
          <dt>操作人</dt>
          <dd>{{ selected.user_name || selected.user_id || '未记录' }}</dd>
        </div>
        <div>
          <dt>操作类型</dt>
          <dd>{{ selected.action }}</dd>
        </div>
        <div>
          <dt>时间</dt>
          <dd>{{ dateText(selected.create_time) }}</dd>
        </div>
        <div>
          <dt>对象 ID</dt>
          <dd>{{ selected.target_id || '—' }}</dd>
        </div>
      </dl>
      <pre class="detail-json mt-5">{{ outputText(selected.detail) }}</pre>
    </template>
  </AppDialog>
</template>
