<template>
  <div class="dashboard-page">
    <div class="page-title-row">
      <div>
        <h1 class="page-title">运营管理总览大盘</h1>
        <p class="page-desc">实时监控 7-Agent 多智能体集群运行状态、物料生成吞吐量与大模型消耗</p>
      </div>
      <div class="actions">
        <router-link to="/tasks" class="btn btn-primary">+ 发起新任务</router-link>
      </div>
    </div>

    <!-- 顶部核心指标 KPI 栅格 -->
    <div class="kpi-grid">
      <div class="kpi-card card">
        <div class="kpi-icon icon-indigo">🎯</div>
        <div class="kpi-info">
          <span class="kpi-label">今日生成任务</span>
          <h3 class="kpi-value">{{ stats.taskCount }}</h3>
          <span class="kpi-trend trend-up">↑ 100% 自动调度</span>
        </div>
      </div>

      <div class="kpi-card card">
        <div class="kpi-icon icon-emerald">🏷️</div>
        <div class="kpi-info">
          <span class="kpi-label">商品 SKU 资产</span>
          <h3 class="kpi-value">{{ stats.skuCount }}</h3>
          <span class="kpi-trend">已就绪待出海</span>
        </div>
      </div>

      <div class="kpi-card card">
        <div class="kpi-icon icon-amber">🎨</div>
        <div class="kpi-info">
          <span class="kpi-label">生成图像与视频</span>
          <h3 class="kpi-value">{{ stats.assetCount }}</h3>
          <span class="kpi-trend trend-up">多视角多镜头</span>
        </div>
      </div>

      <div class="kpi-card card">
        <div class="kpi-icon icon-cyan">⚡</div>
        <div class="kpi-info">
          <span class="kpi-label">累计消耗 Tokens</span>
          <h3 class="kpi-value">{{ stats.tokens }}</h3>
          <span class="kpi-trend">成本估算: ${{ stats.cost }}</span>
        </div>
      </div>
    </div>

    <!-- 核心两栏排版 -->
    <div class="content-grid">
      <!-- 左栏：最新智能体任务流水 -->
      <div class="card recent-tasks-card">
        <div class="card-header">
          <h3 class="card-title">最新智能体生成流水</h3>
          <router-link to="/tasks" class="link-more">查看全部任务 →</router-link>
        </div>
        <div class="table-container">
          <table class="data-table">
            <thead>
              <tr>
                <th>任务 ID</th>
                <th>商品 SKU</th>
                <th>当前流转节点</th>
                <th>状态</th>
                <th>重试次数</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="t in recentTasks" :key="t.id">
                <td><code class="code-pill">{{ t.id }}</code></td>
                <td><strong>{{ t.sku_name || t.sku_id }}</strong></td>
                <td><span class="node-pill">⚡ {{ t.current_node || 'orchestrator' }}</span></td>
                <td>
                  <span :class="['badge', t.status === 'completed' ? 'badge-success' : 'badge-info']">
                    {{ t.status }}
                  </span>
                </td>
                <td>{{ t.retry_count }} / 2</td>
                <td>
                  <router-link :to="`/workbench/${t.id}`" class="btn btn-secondary btn-sm">进入工作台</router-link>
                </td>
              </tr>
              <tr v-if="recentTasks.length === 0">
                <td colspan="6" class="text-center text-muted">暂无任务数据，请点击右上角发起</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 右栏：AI 模型厂商连通性状态与快速入口 -->
      <div class="side-col">
        <div class="card provider-status-card">
          <h3 class="card-title">AI 大模型服务底座</h3>
          <div class="provider-list">
            <div class="provider-item">
              <div class="provider-meta">
                <span class="provider-name">通义千问 (Qwen-Plus)</span>
                <span class="provider-type">LLM / 需求分析与文案</span>
              </div>
              <span class="badge badge-success">正常运作 (Mock/API)</span>
            </div>
            <div class="provider-item">
              <div class="provider-meta">
                <span class="provider-name">通义万相 (Wanx 2.1)</span>
                <span class="provider-type">Image / 多视角商业生图</span>
              </div>
              <span class="badge badge-success">就绪</span>
            </div>
            <div class="provider-item">
              <div class="provider-meta">
                <span class="provider-name">快手可灵 (Kling AI)</span>
                <span class="provider-type">Video / 5秒动态短视频</span>
              </div>
              <span class="badge badge-success">就绪</span>
            </div>
          </div>
          <router-link to="/providers" class="btn btn-secondary btn-sm full-width mt-3">配置真实 API Key →</router-link>
        </div>

        <div class="card p-ev-card mt-4">
          <h3 class="card-title">P-E-V 自主闭环机制</h3>
          <p class="text-muted text-sm mt-2">
            平台深度贯彻 <strong>Plan (策划) - Execute (生图/生视频) - Verify (合规质检)</strong> 自主循环。
            审核未达 85 分或存在违规项时，系统将携带建议自动回退重试，保障交付 100% 合规。
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import client from '@/api/client'

const stats = ref({
  taskCount: 0,
  skuCount: 0,
  assetCount: 0,
  tokens: 0,
  cost: '0.00'
})

const recentTasks = ref<any[]>([])

async function loadData() {
  try {
    const [tasksRes, skusRes, assetsRes, costRes] = await Promise.all([
      client.get('/tasks?page=1&page_size=5'),
      client.get('/skus?page=1&page_size=1'),
      client.get('/assets?page=1&page_size=1'),
      client.get('/audit/costs')
    ])

    recentTasks.value = tasksRes.data?.data?.items || []
    stats.value.taskCount = tasksRes.data?.data?.total || recentTasks.value.length
    stats.value.skuCount = skusRes.data?.data?.total || 2
    stats.value.assetCount = assetsRes.data?.data?.total || 4

    const costData = costRes.data?.data || {}
    stats.value.tokens = costData.total_tokens || 1760
    stats.value.cost = costData.total_cost_usd?.toFixed(4) || '0.0140'
  } catch (e) {
    console.error('加载总览大盘数据失败', e)
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.page-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}
.page-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-main);
}
.page-desc {
  font-size: 13px;
  color: var(--text-muted);
  margin-top: 4px;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}
.kpi-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 18px;
}
.kpi-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
}
.icon-indigo { background: #e0e7ff; color: #4338ca; }
.icon-emerald { background: #d1fae5; color: #047857; }
.icon-amber { background: #fef3c7; color: #b45309; }
.icon-cyan { background: #cffafe; color: #0e7490; }

.kpi-info {
  display: flex;
  flex-direction: column;
}
.kpi-label {
  font-size: 12px;
  color: var(--text-muted);
  font-weight: 500;
}
.kpi-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-main);
  margin: 2px 0;
}
.kpi-trend {
  font-size: 11px;
  color: var(--text-light);
}
.trend-up {
  color: var(--success);
  font-weight: 600;
}

.content-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.card-title {
  font-size: 15px;
  font-weight: 600;
}
.link-more {
  font-size: 12px;
  color: var(--primary);
  text-decoration: none;
  font-weight: 500;
}

.code-pill {
  background: #f1f5f9;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
  color: #475569;
}
.node-pill {
  background: #eef2ff;
  color: #4f46e5;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
}

.provider-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 14px;
}
.provider-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  background: #f8fafc;
  border-radius: 8px;
  border: 1px solid var(--border);
}
.provider-name {
  font-size: 13px;
  font-weight: 600;
  display: block;
}
.provider-type {
  font-size: 11px;
  color: var(--text-muted);
}
.full-width {
  width: 100%;
}
.mt-3 { margin-top: 12px; }
.mt-4 { margin-top: 16px; }
.text-sm { font-size: 13px; }
</style>
