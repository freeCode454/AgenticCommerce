<template>
  <div class="compliance-page">
    <div class="page-title-row">
      <div>
        <h1 class="page-title">合规风控与质检中心</h1>
        <p class="page-desc">实时管控商标侵权、平台违禁词与广告法绝对化夸大宣称</p>
      </div>
    </div>

    <!-- 在线实时合规筛查工具卡片 -->
    <div class="card live-checker-card mb-4">
      <h3 class="card-title mb-2">⚡ 在线出海文案合规即时筛查</h3>
      <p class="text-sm text-muted mb-3">输入待审核商品标题或文案，一键调用合规大模型与关键词库进行智能风控体检</p>
      <div class="checker-form">
        <div class="form-group">
          <label class="form-label">标题 (Title)</label>
          <input type="text" v-model="checkTitle" class="form-input" placeholder="输入待测标题" />
        </div>
        <div class="form-group">
          <label class="form-label">文案内容 (Content / Bullets)</label>
          <textarea v-model="checkContent" class="form-textarea" rows="3" placeholder="输入待测描述内容"></textarea>
        </div>
        <div class="checker-actions">
          <button class="btn btn-primary" @click="runLiveCheck" :disabled="checking">
            {{ checking ? '智能筛查中...' : '🔍 立即合规检测' }}
          </button>
        </div>
      </div>

      <!-- 检测结果展示 -->
      <div v-if="checkResult" class="check-result-box mt-3">
        <div class="result-header">
          <div class="result-score">
            得分: <strong>{{ checkResult.score }}</strong> 分
          </div>
          <span :class="['badge', checkResult.passed ? 'badge-success' : 'badge-danger']">
            {{ checkResult.passed ? '合规通过' : '存在违规风险' }}
          </span>
        </div>
        <div v-if="checkResult.violations?.length" class="violations-list mt-2">
          <div v-for="(v, i) in checkResult.violations" :key="i" class="violation-item">
            ⚠️ {{ v }}
          </div>
        </div>
        <div class="suggestions-list mt-2">
          <span class="text-muted text-xs">优化建议:</span>
          <ul>
            <li v-for="(s, i) in checkResult.suggestions" :key="i" class="text-sm">{{ s }}</li>
          </ul>
        </div>
      </div>
    </div>

    <!-- 历史生成任务质检报告流水 -->
    <div class="card">
      <div class="card-header">
        <h3 class="card-title">历史任务质检评估流水</h3>
      </div>
      <div class="table-container mt-3">
        <table class="data-table">
          <thead>
            <tr>
              <th>报告 ID</th>
              <th>关联任务</th>
              <th>商品 SKU</th>
              <th>综合得分</th>
              <th>审核结果</th>
              <th>各维度明细</th>
              <th>生成时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in reports" :key="r.id">
              <td><code class="code-pill">{{ r.id }}</code></td>
              <td>{{ r.task_id }}</td>
              <td><strong>{{ r.sku_name }}</strong></td>
              <td><strong class="score-text">{{ r.score }} 分</strong></td>
              <td>
                <span :class="['badge', r.passed ? 'badge-success' : 'badge-danger']">
                  {{ r.passed ? 'PASSED' : 'RETRY' }}
                </span>
              </td>
              <td>
                <div class="dims-inline">
                  <span v-for="(v, k) in r.dimensions" :key="k" class="dim-pill">
                    {{ k }}: {{ v }}
                  </span>
                </div>
              </td>
              <td>{{ r.create_time ? new Date(r.create_time).toLocaleString() : '-' }}</td>
            </tr>
            <tr v-if="reports.length === 0">
              <td colspan="7" class="text-center text-muted p-4">暂无审核报告</td>
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

const reports = ref<any[]>([])
const checkTitle = ref('超轻折叠椅 - 顶级品质')
const checkContent = ref('采用世界第一的航天铝合金材料，绝对100%安全，户外露营必备。')
const checking = ref(false)
const checkResult = ref<any>(null)

async function loadReports() {
  try {
    const res = await client.get('/compliance/reports?page=1&page_size=20')
    reports.value = res.data?.data?.items || []
  } catch (e) {
    console.error(e)
  }
}

async function runLiveCheck() {
  if (!checkTitle.value && !checkContent.value) return
  checking.value = true
  try {
    const res = await client.post('/compliance/check', {
      title: checkTitle.value,
      content: checkContent.value,
      target_platform: 'amazon'
    })
    checkResult.value = res.data?.data
  } catch (e) {
    alert('检测失败')
  } finally {
    checking.value = false
  }
}

onMounted(() => {
  loadReports()
})
</script>

<style scoped>
.page-title-row { margin-bottom: 24px; }
.page-title { font-size: 22px; font-weight: 700; }
.page-desc { font-size: 13px; color: var(--text-muted); margin-top: 4px; }

.live-checker-card {
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid #c7d2fe;
}
.check-result-box {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 14px 18px;
}
.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.result-score { font-size: 16px; color: #1e293b; }
.violation-item {
  color: #dc2626;
  font-size: 12.5px;
  background: #fee2e2;
  padding: 4px 10px;
  border-radius: 4px;
  margin-top: 4px;
}

.dims-inline { display: flex; gap: 6px; flex-wrap: wrap; }
.dim-pill {
  background: #f1f5f9;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11px;
}
.score-text { color: #047857; font-size: 14px; }
.code-pill { background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 12px; }
</style>
