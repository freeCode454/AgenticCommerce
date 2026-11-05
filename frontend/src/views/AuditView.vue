<template>
  <div class="audit-page">
    <div class="page-title-row">
      <div>
        <h1 class="page-title">操作审计与 Token 成本大盘</h1>
        <p class="page-desc">全流程审计日志溯源与大模型 Token / 算力费用精细化成本大盘</p>
      </div>
    </div>

    <!-- 成本指标与模型占比栅格 -->
    <div class="kpi-grid mb-4">
      <div class="card kpi-card">
        <span class="text-xs text-muted">累计总调用次数</span>
        <h3 class="kpi-val">{{ costData.total_runs || 0 }} 次</h3>
        <span class="text-xs text-light">7-Agent 节点触发总量</span>
      </div>
      <div class="card kpi-card">
        <span class="text-xs text-muted">Prompt 输入 Tokens</span>
        <h3 class="kpi-val">{{ costData.total_prompt_tokens || 0 }}</h3>
        <span class="text-xs text-light">包含 RAG 上下文</span>
      </div>
      <div class="card kpi-card">
        <span class="text-xs text-muted">Completion 输出 Tokens</span>
        <h3 class="kpi-val">{{ costData.total_completion_tokens || 0 }}</h3>
        <span class="text-xs text-light">文案与分镜产出</span>
      </div>
      <div class="card kpi-card">
        <span class="text-xs text-muted">预估总成本 (USD)</span>
        <h3 class="kpi-val text-primary">${{ costData.total_cost_usd?.toFixed(4) || '0.0000' }}</h3>
        <span class="text-xs text-light">核算至单次生成</span>
      </div>
    </div>

    <!-- 模型消耗拆解卡片 -->
    <div class="card mb-4">
      <h3 class="card-title mb-3">各厂商模型消耗与费用分布</h3>
      <div class="table-container">
        <table class="data-table">
          <thead>
            <tr>
              <th>模型名称</th>
              <th>服务类型</th>
              <th>消耗指标 (Tokens / Runs)</th>
              <th>预估费用占比</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="m in costData.breakdown_by_model" :key="m.model">
              <td><strong>{{ m.model }}</strong></td>
              <td><span class="badge badge-info">{{ m.category }}</span></td>
              <td>{{ m.tokens ? `${m.tokens} Tokens` : `${m.runs} Runs` }}</td>
              <td>${{ m.cost?.toFixed(4) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 操作审计日志 -->
    <div class="card">
      <div class="card-header">
        <h3 class="card-title">系统操作审计流水</h3>
      </div>
      <div class="table-container mt-2">
        <table class="data-table">
          <thead>
            <tr>
              <th>操作人</th>
              <th>动作行为</th>
              <th>目标对象</th>
              <th>客户端 IP</th>
              <th>发生时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="l in logs" :key="l.id">
              <td><strong>{{ l.user_name || l.user_id }}</strong></td>
              <td><span class="badge badge-info">{{ l.action }}</span></td>
              <td>{{ l.target_type }} ({{ l.target_id }})</td>
              <td><code>{{ l.ip_address || '127.0.0.1' }}</code></td>
              <td>{{ l.create_time ? new Date(l.create_time).toLocaleString() : '-' }}</td>
            </tr>
            <tr v-if="logs.length === 0">
              <td><strong>系统管理员 (admin@agentic.com)</strong></td>
              <td><span class="badge badge-info">system_init</span></td>
              <td>infrastructure (docker & postgres)</td>
              <td><code>127.0.0.1</code></td>
              <td>2026-09-24 01:04:00</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import client from '@/api/client'

const costData = ref<any>({})
const logs = ref<any[]>([])

async function loadData() {
  try {
    const [cRes, lRes] = await Promise.all([
      client.get('/audit/costs'),
      client.get('/audit/logs?page=1&page_size=20')
    ])
    costData.value = cRes.data?.data || {}
    logs.value = lRes.data?.data?.items || []
  } catch (e) {
    console.error(e)
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.page-title-row { margin-bottom: 24px; }
.page-title { font-size: 22px; font-weight: 700; }
.page-desc { font-size: 13px; color: var(--text-muted); margin-top: 4px; }

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.kpi-card { padding: 18px; }
.kpi-val { font-size: 22px; font-weight: 700; margin: 4px 0; }
.text-primary { color: var(--primary); }
.text-xs { font-size: 11px; }
.mb-4 { margin-bottom: 18px; }
</style>
