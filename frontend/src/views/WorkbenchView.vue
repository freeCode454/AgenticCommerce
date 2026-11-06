<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import client from '@/api/client'
import { useTaskWorkspace } from '@/composables/useTaskWorkspace'
import { createSubmissionKey } from '@/utils/submissionKey'
import { useUiStore } from '@/stores/ui'
import { dateText, errorMessage, fullCopy, moneyText, outputText } from '@/utils/format'
import PageHeading from '@/components/ui/PageHeading.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import PageState from '@/components/ui/PageState.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import AppDialog from '@/components/ui/AppDialog.vue'
import MediaPreview from '@/components/ui/MediaPreview.vue'
import ReviewResult from '@/components/ui/ReviewResult.vue'
const route = useRoute(),
  ui = useUiStore(),
  taskId = computed(() => String(route.params.taskId || ''))
const {
  detail,
  nodes,
  latest,
  loading,
  refreshing,
  error,
  errorCode,
  connection,
  running,
  refresh,
  reconnectNow,
} = useTaskWorkspace(taskId)
const tab = ref('copy'),
  drawer = ref(false),
  selected = ref(''),
  retrying = ref(false)
const retryKey = createSubmissionKey()
const remoteStatuses: Record<string, string> = {
  submitting: '正在提交',
  submitted: '已提交',
  pending: '排队中',
  running: '生成中',
  succeeded: '已生成',
  failed: '生成失败',
  canceled: '已取消',
  unknown: '已过期或不可查询',
  submission_unknown: '提交结果待核实',
}
const steps = [
  { key: 'orchestrator', name: '任务准备' },
  { key: 'requirement_analyzer', name: '需求分析' },
  { key: 'creative_planner', name: '文案创作' },
  { key: 'visual_designer', name: '视觉设计' },
  { key: 'image_generator', name: '图片生成' },
  { key: 'video_generator', name: '视频生成' },
  { key: 'quality_reviewer', name: '质量审核' },
]
const history = computed(() =>
  nodes.value
    .filter((node) => node.node_name === selected.value)
    .slice()
    .reverse(),
)
const selectedName = computed(
  () => steps.find((step) => step.key === selected.value)?.name || '节点详情',
)
const imageAssets = computed(
    () => detail.value?.assets.filter((asset) => asset.type === 'image') || [],
  ),
  videoAssets = computed(() => detail.value?.assets.filter((asset) => asset.type === 'video') || [])
const completed = computed(
  () => Object.values(latest.value).filter((node) => node.status === 'success').length,
)
const reviewReport = computed(() =>
  detail.value?.compliance_report
    ? {
        ...detail.value.compliance_report,
        status:
          detail.value.task.status === 'review_required'
            ? 'outdated'
            : detail.value.compliance_report.status,
      }
    : null,
)
async function retry() {
  if (retrying.value || running.value) return
  if (
    !(await ui.confirm(
      '重新执行这个任务',
      '将从头执行完整生成，可能覆盖手工编辑的文案，并再次产生模型费用。',
      '重新生成',
    ))
  )
    return
  retrying.value = true
  try {
    await client.post(`/tasks/${taskId.value}/run`, undefined, {
      headers: { 'Idempotency-Key': retryKey.forPayload(taskId.value) },
    })
    retryKey.reset()
    ui.notify('已重新创建执行请求')
    await refresh()
    reconnectNow()
  } catch (cause) {
    ui.notify(errorMessage(cause), 'error')
  } finally {
    retrying.value = false
  }
}
function openNode(key: string) {
  selected.value = key
  drawer.value = true
}
</script>
<template>
  <PageHeading
    title="生成工作台"
    :description="detail?.task.sku_name || '查看每一步创作进展与真实产物。'"
    eyebrow="让每一步创作，都清晰可见"
  >
    <RouterLink to="/tasks" class="btn btn-secondary">
      <AppIcon name="arrow-left" :size="17" />
      返回任务
    </RouterLink>
  </PageHeading>
  <PageState
    :loading="loading"
    :error-code="errorCode"
    :error="!detail ? error : ''"
    :empty="!detail"
    title="没有找到任务"
    @retry="refresh"
  >
    <template v-if="detail">
      <div v-if="error" class="notice notice-warning" role="alert">
        <AppIcon name="warning" />
        <span>{{ error }} 当前展示上次成功获取的内容。</span>
        <button class="text-button" @click="refresh">重新加载</button>
      </div>
      <div class="workbench-summary">
        <div class="row wrap">
          <StatusBadge :status="detail.task.status" />
          <span class="code-pill">{{ detail.task.sku_code || detail.task.id }}</span>
          <span class="subtle">创建于 {{ dateText(detail.task.create_time) }}</span>
        </div>
        <div class="row wrap">
          <span class="connection-status">
            <AppIcon name="wifi" :size="16" />
            {{ connection }}
          </span>
          <button
            v-if="!['实时连接正常', '正在连接', '正在重新连接'].includes(connection)"
            class="text-button"
            @click="reconnectNow"
          >
            重新连接
          </button>
          <button class="icon-button" aria-label="刷新任务" :disabled="refreshing" @click="refresh">
            <AppIcon name="refresh" :size="17" />
          </button>
          <button
            v-if="['failed', 'review_required'].includes(detail.task.status)"
            class="btn btn-secondary btn-sm"
            :disabled="retrying"
            @click="retry"
          >
            <span v-if="retrying" class="spinner" />
            重新生成
          </button>
        </div>
      </div>
      <div v-if="detail.task.status === 'failed'" class="notice notice-danger">
        <AppIcon name="warning" />
        <span>
          {{
            detail.task.error_message ||
            '任务执行失败。请查看失败节点的执行记录，检查模型配置或重试。'
          }}
        </span>
      </div>
      <div v-if="detail.task.status === 'review_required'" class="notice notice-warning">
        <AppIcon name="info" />
        <span>
          文案修改后，旧审核已失效。当前只支持完整重新生成，可能覆盖手工编辑的文案并产生费用。
        </span>
      </div>
      <div v-if="detail.task.status === 'pending'" class="notice">
        <AppIcon name="clock" />
        <span>任务已保存，正在排队。尚未开始的任务会在服务恢复后继续执行。</span>
      </div>
      <div v-else-if="running" class="notice">
        <AppIcon name="clock" />
        <span>
          创作仍在执行中，已记录 {{ completed }} / 7
          个节点完成状态。图片与视频生成可能需要较长时间。
        </span>
      </div>
      <section
        v-if="detail.remote_jobs?.length"
        class="panel remote-video mb-5"
        aria-label="远端视频任务"
      >
        <h2>视频生成状态</h2>
        <p v-if="running && detail.task.next_poll_at" class="subtle">
          视频已提交，服务恢复后会继续查询已有任务，跳过文案和图片生成。 下次查询：{{
            dateText(detail.task.next_poll_at)
          }}
        </p>
        <p class="subtle">视频费用尚未从厂商账单核实，未计入当前费用合计。</p>
        <div v-for="job in detail.remote_jobs" :key="job.id" class="form-section">
          <div class="row wrap">
            <span>第 {{ job.round }} 轮 · {{ job.model }}</span>
            <span class="tag">{{ remoteStatuses[job.status] || '查询状态待核实' }}</span>
          </div>
          <p v-if="job.error_message" class="form-error" role="status">{{ job.error_message }}</p>
          <details v-if="job.remote_id" class="spaced">
            <summary>核对厂商任务</summary>
            <p class="break-word">任务 ID：{{ job.remote_id }}</p>
            <p class="subtle">如需核对生成结果或费用，可使用此 ID 在厂商控制台查询。</p>
          </details>
        </div>
      </section>
      <div class="workbench-layout">
        <aside class="node-list">
          <h2>创作流程</h2>
          <button
            v-for="(step, index) in steps"
            :key="step.key"
            class="node-button"
            :class="{
              'node-complete': latest[step.key]?.status === 'success',
              'node-failed': latest[step.key]?.status === 'failed',
            }"
            @click="openNode(step.key)"
          >
            <span>
              <AppIcon v-if="latest[step.key]?.status === 'success'" name="check" :size="15" />
              <AppIcon v-else-if="latest[step.key]?.status === 'failed'" name="close" :size="15" />
              <template v-else>{{ index + 1 }}</template>
            </span>
            <span>
              <strong>{{ step.name }}</strong>
              <small>
                {{
                  latest[step.key]
                    ? `${latest[step.key].elapsed_ms || 0} ms · 查看记录`
                    : '暂无执行记录'
                }}
              </small>
            </span>
            <AppIcon name="chevron-right" :size="14" />
          </button>
        </aside>
        <section class="panel">
          <div class="result-tabs" role="tablist" aria-label="生成产物">
            <button
              v-for="item in [
                { key: 'copy', name: '文案', icon: 'file' },
                { key: 'images', name: '图片', icon: 'image' },
                { key: 'videos', name: '视频', icon: 'video' },
                { key: 'review', name: '审核', icon: 'shield' },
              ]"
              :key="item.key"
              role="tab"
              :aria-selected="tab === item.key"
              :class="{ active: tab === item.key }"
              @click="tab = item.key"
            >
              <AppIcon :name="item.icon" :size="16" />
              {{ item.name }}
            </button>
          </div>
          <div class="result-body" role="tabpanel">
            <template v-if="tab === 'copy'">
              <template v-if="detail.copy">
                <div class="row between wrap">
                  <span class="tag">英文文案</span>
                  <button class="text-button" @click="ui.copy(fullCopy(detail.copy))">
                    <AppIcon name="copy" :size="16" />
                    复制文案
                  </button>
                </div>
                <h2 class="spaced">{{ detail.copy.title }}</h2>
                <h3>核心卖点</h3>
                <ul class="bullets">
                  <li v-for="(bullet, index) in detail.copy.bullets" :key="index">
                    {{ bullet }}
                  </li>
                </ul>
                <h3>商品描述</h3>
                <p class="prose">{{ detail.copy.description || '暂无描述' }}</p>
                <h3>关键词</h3>
                <div class="chip-list">
                  <span v-for="word in detail.copy.keywords" :key="word" class="tag">
                    {{ word }}
                  </span>
                </div>
                <RouterLink :to="`/copies?task_id=${taskId}`" class="btn btn-secondary spaced">
                  <AppIcon name="edit" :size="16" />
                  到文案库编辑
                </RouterLink>
              </template>
              <PageState
                v-else
                empty
                title="文案还在路上"
                description="文案节点完成并保存后，会显示在这里。"
                icon="file"
              />
            </template>
            <template v-else-if="tab === 'images'">
              <div v-if="imageAssets.length" class="media-grid">
                <article v-for="asset in imageAssets" :key="asset.id" class="media-card">
                  <MediaPreview :src="asset.url" :alt="detail.task.sku_name || '生成图片'" />
                  <div class="media-card-body">
                    <h3>
                      {{
                        { main: '商品主图', scene: '场景图', detail: '细节图' }[
                          asset.sub_type || ''
                        ] ||
                        asset.sub_type ||
                        '商品图片'
                      }}
                    </h3>
                    <span v-if="asset.is_mock" class="status-badge status-warning">模拟素材</span>
                  </div>
                </article>
              </div>
              <PageState
                v-else
                empty
                title="还没有生成图片"
                description="图片节点完成并保存后，会显示在这里。"
                icon="image"
              />
            </template>
            <template v-else-if="tab === 'videos'">
              <div v-if="videoAssets.length" class="stack">
                <article v-for="asset in videoAssets" :key="asset.id" class="media-card">
                  <MediaPreview :src="asset.url" type="video" :controls="true" alt="生成视频" />
                  <div class="media-card-body">
                    <h3>商品视频</h3>
                    <span v-if="asset.is_mock" class="status-badge status-warning">模拟素材</span>
                  </div>
                </article>
              </div>
              <PageState
                v-else
                empty
                title="还没有生成视频"
                description="视频节点完成并保存后，可在这里播放。"
                icon="video"
              />
            </template>
            <template v-else>
              <ReviewResult v-if="reviewReport" :report="reviewReport" />
              <PageState
                v-else
                empty
                title="审核报告尚未生成"
                description="审核节点执行后，会显示真实评分及改进建议。"
                icon="shield"
              />
              <RouterLink
                v-if="detail.task.status === 'completed'"
                to="/packages"
                class="btn btn-secondary spaced"
              >
                查看交付中心
                <AppIcon name="arrow-right" :size="16" />
              </RouterLink>
            </template>
          </div>
        </section>
      </div>
    </template>
  </PageState>
  <AppDialog
    v-model="drawer"
    :title="selectedName"
    description="以下为真实记录的执行结果，最新记录在前。"
    drawer
  >
    <PageState
      :empty="!history.length"
      title="暂无执行记录"
      description="节点完成或报告错误后，记录会显示在这里。"
    >
      <article v-for="(record, index) in history" :key="record.id || index" class="card spaced">
        <div class="row between wrap">
          <StatusBadge :status="record.status" />
          <span class="subtle">{{ dateText(record.create_time) }}</span>
        </div>
        <dl class="details-list spaced">
          <div>
            <dt>执行耗时</dt>
            <dd>{{ record.elapsed_ms ?? 0 }} ms</dd>
          </div>
          <div>
            <dt>输入 / 输出 Tokens</dt>
            <dd>
              {{ record.prompt_tokens ?? 0 }} /
              {{ record.completion_tokens ?? 0 }}
            </dd>
          </div>
          <div>
            <dt>预估费用</dt>
            <dd>{{ moneyText(record.cost) }} USD</dd>
          </div>
        </dl>
        <div v-if="record.status === 'failed'" class="notice notice-danger spaced">
          <span>
            节点返回的失败信息：
            <span class="prose">
              {{ outputText(record.output_data) || '当前记录没有提供具体原因。' }}
            </span>
          </span>
        </div>
        <details class="details-toggle">
          <summary>查看输入与输出快照</summary>
          <h3 class="spaced">输入</h3>
          <pre class="detail-json">{{ outputText(record.input_data) }}</pre>
          <h3>输出</h3>
          <pre class="detail-json">{{ outputText(record.output_data) }}</pre>
        </details>
      </article>
    </PageState>
  </AppDialog>
</template>

<style scoped>
.remote-video {
  padding: 22px;
  min-width: 0;
  overflow-wrap: anywhere;
}
.remote-video p {
  overflow-wrap: anywhere;
}
</style>
