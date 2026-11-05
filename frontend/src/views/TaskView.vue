<template>
  <div class="task-page">
    <div class="page-title-row">
      <div>
        <h1 class="page-title">智能体生成任务</h1>
        <p class="page-desc">管理并追踪全量商品自动化多智能体物料生成流</p>
      </div>
      <div class="actions">
        <button class="btn btn-primary" @click="showCreateModal = true">+ 发起生成任务</button>
      </div>
    </div>

    <!-- 筛选工具栏 -->
    <div class="card filter-bar mb-4">
      <div class="filter-group">
        <label>任务状态:</label>
        <select v-model="statusFilter" class="form-select" @change="loadTasks">
          <option value="">全部状态</option>
          <option value="running">running (流转中)</option>
          <option value="completed">completed (已完成)</option>
          <option value="failed">failed (异常)</option>
        </select>
      </div>
      <button class="btn btn-secondary btn-sm" @click="loadTasks">查询刷新</button>
    </div>

    <!-- 任务数据表格 -->
    <div class="table-container">
      <table class="data-table">
        <thead>
          <tr>
            <th>任务 ID</th>
            <th>关联商品 SKU</th>
            <th>当前节点</th>
            <th>状态</th>
            <th>重试次数</th>
            <th>创建时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in tasks" :key="t.id">
            <td><code class="code-pill">{{ t.id }}</code></td>
            <td>
              <strong>{{ t.sku_name || t.sku_id }}</strong>
              <div class="text-xs text-muted">{{ t.sku_code }}</div>
            </td>
            <td><span class="node-pill">⚡ {{ t.current_node || 'orchestrator' }}</span></td>
            <td>
              <span :class="['badge', t.status === 'completed' ? 'badge-success' : 'badge-info']">
                {{ t.status }}
              </span>
            </td>
            <td>{{ t.retry_count }} 次</td>
            <td>{{ t.create_time ? new Date(t.create_time).toLocaleString() : '-' }}</td>
            <td>
              <router-link :to="`/workbench/${t.id}`" class="btn btn-primary btn-sm">工作台</router-link>
            </td>
          </tr>
          <tr v-if="tasks.length === 0">
            <td colspan="7" class="text-center text-muted p-4">暂无匹配任务记录</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 发起新任务弹窗 -->
    <div v-if="showCreateModal" class="modal-overlay" @click.self="showCreateModal = false">
      <div class="modal-content">
        <h3 class="modal-title mb-4">发起 7-Agent 多智能体生成任务</h3>
        <div class="form-group">
          <label class="form-label">选择目标出海商品 SKU</label>
          <select v-model="selectedSkuId" class="form-select">
            <option v-for="s in skuOptions" :key="s.id" :value="s.id">
              [{{ s.code }}] {{ s.name }} ({{ s.category }})
            </option>
          </select>
        </div>

        <div class="form-group">
          <label class="form-label">目标电商市场与平台</label>
          <select v-model="taskPlatform" class="form-select">
            <option value="amazon">Amazon 亚马逊 (北美站)</option>
            <option value="shopify">Shopify 独立站</option>
            <option value="tiktok">TikTok Shop (美区/东南亚)</option>
          </select>
        </div>

        <div class="form-group">
          <label class="form-label">最大自主审核重试次数 (P-E-V 闭环)</label>
          <input type="number" v-model="maxRetries" min="0" max="3" class="form-input" />
        </div>

        <div class="modal-footer mt-4">
          <button class="btn btn-secondary" @click="showCreateModal = false">取消</button>
          <button class="btn btn-primary" @click="submitTask" :disabled="submitting">
            {{ submitting ? '调度中...' : '立即启动 7-Agent 生成' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import client from '@/api/client'

const tasks = ref<any[]>([])
const skuOptions = ref<any[]>([])
const statusFilter = ref('')
const showCreateModal = ref(false)
const selectedSkuId = ref('sku_camp01')
const taskPlatform = ref('amazon')
const maxRetries = ref(2)
const submitting = ref(false)

async function loadTasks() {
  try {
    let url = '/tasks?page=1&page_size=20'
    if (statusFilter.value) url += `&status=${statusFilter.value}`
    const res = await client.get(url)
    tasks.value = res.data?.data?.items || []
  } catch (e) {
    console.error(e)
  }
}

async function loadSkus() {
  try {
    const res = await client.get('/skus?page=1&page_size=50')
    skuOptions.value = res.data?.data?.items || []
    if (skuOptions.value.length > 0) {
      selectedSkuId.value = skuOptions.value[0].id
    }
  } catch (e) {
    console.error(e)
  }
}

async function submitTask() {
  submitting.value = true
  try {
    await client.post('/tasks', {
      sku_id: selectedSkuId.value,
      config: {
        platform: taskPlatform.value,
        language: 'en',
        max_retries: maxRetries.value
      }
    })
    showCreateModal.value = false
    alert('任务创建成功！7-Agent 工作流已在后台开始自主生成。')
    loadTasks()
  } catch (e) {
    alert('任务发起失败')
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  loadTasks()
  loadSkus()
})
</script>

<style scoped>
.page-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.page-title { font-size: 22px; font-weight: 700; }
.page-desc { font-size: 13px; color: var(--text-muted); margin-top: 4px; }

.filter-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 18px;
}
.filter-group {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13.5px;
}

.code-pill {
  background: #f1f5f9;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
}
.node-pill {
  background: #eef2ff;
  color: #4f46e5;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
}
.text-xs { font-size: 11px; }
.mb-4 { margin-bottom: 16px; }
.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
