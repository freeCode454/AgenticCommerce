<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import client from '@/api/client'
import type { Task, CostSummary, ApiResponse, PageData } from '@/types'
import { dateText, moneyText, numberText, platformText } from '@/utils/format'
import PageHeading from '@/components/ui/PageHeading.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import PageState from '@/components/ui/PageState.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import TaskCreateDialog from '@/components/ui/TaskCreateDialog.vue'
const router = useRouter(),
  showCreate = ref(false),
  loading = ref(true),
  tasks = ref<Task[]>([]),
  tasksError = ref('')
const counts = ref<{
  sku?: number
  tasks?: number
  assets?: number
  cost?: number
}>({})
const errors = ref(false)
let controller: AbortController | undefined,
  sequence = 0
const greeting = computed(() => {
  const hour = new Date().getHours()
  return hour < 12 ? '上午好，创作团队。' : hour < 18 ? '下午好，创作团队。' : '晚上好，创作团队。'
})
async function load() {
  const id = ++sequence
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  errors.value = false
  tasksError.value = ''
  const config = { signal: controller.signal }
  const results = await Promise.allSettled([
    client.get<ApiResponse<PageData<Task>>>('/tasks', {
      ...config,
      params: { page: 1, page_size: 5 },
    }),
    client.get<ApiResponse<PageData<unknown>>>('/skus', {
      ...config,
      params: { page: 1, page_size: 1 },
    }),
    client.get<ApiResponse<PageData<unknown>>>('/assets', {
      ...config,
      params: { page: 1, page_size: 1 },
    }),
    client.get<ApiResponse<CostSummary>>('/audit/costs', config),
  ])
  if (id !== sequence) return
  const [task, sku, asset, cost] = results
  counts.value = {
    tasks: task.status === 'fulfilled' ? task.value.data.data.total : undefined,
    sku: sku.status === 'fulfilled' ? sku.value.data.data.total : undefined,
    assets: asset.status === 'fulfilled' ? asset.value.data.data.total : undefined,
    cost: cost.status === 'fulfilled' ? cost.value.data.data.total_cost_usd : undefined,
  }
  if (task.status === 'fulfilled') tasks.value = task.value.data.data.items
  else tasksError.value = '任务列表暂不可用，请重新加载。'
  errors.value = results.some((result) => result.status === 'rejected')
  loading.value = false
}
onMounted(load)
onUnmounted(() => {
  ++sequence
  controller?.abort()
})
</script>
<template>
  <PageHeading :title="greeting" description="把创作交给 AI，把时间留给更好的生意。">
    <button class="btn btn-primary" @click="showCreate = true">
      <AppIcon name="plus" :size="17" />
      新建生成任务
    </button>
  </PageHeading>
  <section class="welcome-banner">
    <div class="welcome-copy">
      <span class="overline">FROM PRODUCT TO POSSIBILITY</span>
      <h2>好商品，值得被更多人看见。</h2>
      <p>从一份商品资料开始，让文案、图片与视频有序发生。</p>
      <RouterLink class="text-button" to="/skus?new=1">
        录入商品，开启新创作
        <AppIcon name="arrow-right" :size="15" />
      </RouterLink>
    </div>
    <div class="workflow-art" aria-hidden="true">
      <div class="workflow-card">
        <AppIcon name="box" :size="26" />
        <span>商品资料</span>
      </div>
      <AppIcon name="arrow-right" :size="17" />
      <div class="workflow-card dark">
        <AppIcon name="spark" :size="28" />
        <span>AI 创作</span>
      </div>
      <AppIcon name="arrow-right" :size="17" />
      <div class="workflow-card">
        <AppIcon name="shield" :size="26" />
        <span>审核交付</span>
      </div>
    </div>
  </section>
  <div v-if="errors" class="notice notice-warning">
    <AppIcon name="warning" />
    <span>部分数据暂不可用，已保留可用内容。</span>
    <button class="text-button" @click="load">重新加载</button>
  </div>
  <section class="metrics-grid" aria-label="工作空间真实数据">
    <article
      v-for="metric in [
        {
          label: '商品总数',
          value: counts.sku,
          unit: '件',
          icon: 'box',
          description: '已录入的商品资料',
        },
        {
          label: '生成任务',
          value: counts.tasks,
          unit: '项',
          icon: 'layers',
          description: '当前工作空间的全部任务',
        },
        {
          label: '已生成素材',
          value: counts.assets,
          unit: '份',
          icon: 'image',
          description: '文案以外的图片与视频',
        },
      ]"
      :key="metric.label"
      class="metric"
    >
      <div class="metric-top">
        <span>{{ metric.label }}</span>
        <span class="metric-icon"><AppIcon :name="metric.icon" :size="17" /></span>
      </div>
      <div class="metric-number">
        {{ loading ? '—' : numberText(metric.value) }}
        <small v-if="metric.value !== undefined">{{ metric.unit }}</small>
      </div>
      <p>{{ metric.description }}</p>
    </article>
    <article class="metric metric-cost">
      <div class="metric-top">
        <span>累计预估费用</span>
        <span class="metric-icon"><AppIcon name="chart" :size="17" /></span>
      </div>
      <div class="metric-number">
        {{ loading ? '—' : moneyText(counts.cost) }}
      </div>
      <p>USD · 根据节点执行记录汇总</p>
    </article>
  </section>
  <div class="dashboard-columns">
    <section class="panel">
      <header class="panel-heading">
        <div>
          <h2>最近的创作</h2>
          <p>每一步进展，都在这里。</p>
        </div>
        <RouterLink class="text-button" to="/tasks">
          全部任务
          <AppIcon name="arrow-right" :size="14" />
        </RouterLink>
      </header>
      <PageState
        :loading="loading"
        :error="tasksError"
        :empty="!tasks.length"
        title="你的第一份创作，从这里开始"
        description="先录入商品资料，再创建生成任务。"
        @retry="load"
      >
        <template #action>
          <button v-if="(counts.sku || 0) > 0" class="btn btn-primary" @click="showCreate = true">
            <AppIcon name="plus" :size="16" />
            创建第一个生成任务
          </button>
          <RouterLink v-else class="btn btn-primary" to="/skus?new=1">
            <AppIcon name="plus" :size="16" />
            录入第一个商品
          </RouterLink>
        </template>
        <div class="table-scroll">
          <table class="data-table">
            <thead>
              <tr>
                <th>商品 / 任务</th>
                <th>目标平台</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="task in tasks" :key="task.id">
                <td class="table-main">
                  <strong>{{ task.sku_name || '未命名商品' }}</strong>
                  <small>{{ task.sku_code || task.id }} · {{ dateText(task.create_time) }}</small>
                </td>
                <td>
                  <span class="platform-tag">{{ platformText(task.config?.platform) }}</span>
                </td>
                <td><StatusBadge :status="task.status" /></td>
                <td>
                  <RouterLink
                    :to="`/workbench/${task.id}`"
                    class="icon-button"
                    :aria-label="`查看${task.sku_name || '任务'}`"
                  >
                    <AppIcon name="chevron-right" :size="17" />
                  </RouterLink>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </PageState>
    </section>
    <aside class="dashboard-aside stack">
      <section class="launch-panel">
        <span class="overline">
          <AppIcon name="spark" :size="18" />
          LET'S CREATE
        </span>
        <h2>
          下一个好内容，
          <br />
          从这里开始。
        </h2>
        <p>选择真实商品，让 AI 成为你的创作伙伴。</p>
        <button class="btn btn-lime" @click="showCreate = true">
          创建新任务
          <AppIcon name="arrow-right" :size="16" />
        </button>
      </section>
      <section class="brand-tip">
        <AppIcon name="book" :size="23" />
        <div>
          <h3>先让 AI 了解你的品牌</h3>
          <p>加入品牌规范，让每次创作更像你。</p>
          <RouterLink class="text-button" to="/knowledge">
            完善知识库
            <AppIcon name="arrow-right" :size="14" />
          </RouterLink>
        </div>
      </section>
    </aside>
  </div>
  <TaskCreateDialog
    v-if="showCreate"
    v-model="showCreate"
    @created="router.push(`/workbench/${$event}`)"
  />
</template>
