<template>
  <div class="batch-page">
    <div class="page-title-row">
      <div>
        <h1 class="page-title">批次生成调度</h1>
        <p class="page-desc">支持百款 SKU 矩阵式批量下发与多智能体集群高并发处理</p>
      </div>
      <div class="actions">
        <button class="btn btn-primary" @click="showModal = true">+ 新建批量生成批次</button>
      </div>
    </div>

    <!-- 批次列表 -->
    <div class="batch-grid">
      <div v-for="b in batches" :key="b.id" class="batch-card card">
        <div class="batch-header">
          <div>
            <h3 class="batch-name">{{ b.name }}</h3>
            <span class="text-xs text-muted">ID: {{ b.id }}</span>
          </div>
          <span :class="['badge', b.status === 'completed' ? 'badge-success' : 'badge-info']">
            {{ b.status }}
          </span>
        </div>

        <div class="progress-wrap mt-3">
          <div class="progress-meta">
            <span>处理进度:</span>
            <strong>{{ b.completed_count }} / {{ b.total_count }}</strong>
          </div>
          <div class="progress-track">
            <div class="progress-bar" :style="{ width: `${b.total_count ? (b.completed_count/b.total_count)*100 : 0}%` }"></div>
          </div>
        </div>

        <div class="batch-footer mt-4">
          <span class="text-xs text-muted">创建时间: {{ b.create_time ? new Date(b.create_time).toLocaleString() : '-' }}</span>
          <button class="btn btn-secondary btn-sm" @click="viewBatch(b.id)">查看批次详情</button>
        </div>
      </div>

      <div v-if="batches.length === 0" class="empty-state card">
        <p class="text-muted">暂无批次任务，可点击右上角创建批量任务</p>
      </div>
    </div>

    <!-- 新建批次弹窗 -->
    <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
      <div class="modal-content">
        <h3 class="modal-title mb-4">创建多商品批量生成批次</h3>
        <div class="form-group">
          <label class="form-label">批次名称</label>
          <input type="text" v-model="batchName" class="form-input" placeholder="例如: 2026秋季露营装备全量出海" />
        </div>

        <div class="form-group">
          <label class="form-label">选择参与批量生成的 SKU (多选)</label>
          <div class="sku-checkbox-list">
            <label v-for="s in availableSkus" :key="s.id" class="sku-checkbox-item">
              <input type="checkbox" :value="s.id" v-model="selectedSkus" />
              <span>[{{ s.code }}] {{ s.name }}</span>
            </label>
          </div>
        </div>

        <div class="modal-footer mt-4">
          <button class="btn btn-secondary" @click="showModal = false">取消</button>
          <button class="btn btn-primary" @click="submitBatch" :disabled="submitting || !selectedSkus.length">
            {{ submitting ? '下发中...' : `立即下发批次 (${selectedSkus.length}款SKU)` }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import client from '@/api/client'

const batches = ref<any[]>([])
const availableSkus = ref<any[]>([])
const showModal = ref(false)
const batchName = ref('2026秋季户外系列出海批次')
const selectedSkus = ref<string[]>([])
const submitting = ref(false)

async function loadBatches() {
  try {
    const res = await client.get('/batches')
    batches.value = res.data?.data?.items || []
  } catch (e) {
    console.error(e)
  }
}

async function loadSkus() {
  try {
    const res = await client.get('/skus')
    availableSkus.value = res.data?.data?.items || []
    if (availableSkus.value.length > 0) {
      selectedSkus.value = availableSkus.value.map(s => s.id)
    }
  } catch (e) {
    console.error(e)
  }
}

async function submitBatch() {
  if (!batchName.value || !selectedSkus.value.length) return
  submitting.value = true
  try {
    await client.post('/batches', {
      name: batchName.value,
      sku_ids: selectedSkus.value,
      config: { platform: 'amazon', language: 'en' }
    })
    showModal.value = false
    alert('批次已成功下发至智能体集群！')
    loadBatches()
  } catch (e) {
    alert('下发失败')
  } finally {
    submitting.value = false
  }
}

function viewBatch(batchId: string) {
  alert(`批次 ${batchId} 正在由后台多进程 Worker 持续调度`)
}

onMounted(() => {
  loadBatches()
  loadSkus()
})
</script>

<style scoped>
.page-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}
.page-title { font-size: 22px; font-weight: 700; }
.page-desc { font-size: 13px; color: var(--text-muted); margin-top: 4px; }

.batch-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}
.batch-card {
  padding: 18px;
}
.batch-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}
.batch-name { font-size: 16px; font-weight: 600; }
.text-xs { font-size: 11px; }

.progress-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12.5px;
  color: var(--text-muted);
  margin-bottom: 6px;
}
.progress-track {
  height: 8px;
  background: #e2e8f0;
  border-radius: 4px;
  overflow: hidden;
}
.progress-bar {
  height: 100%;
  background: linear-gradient(90deg, #4f46e5, #06b6d4);
  transition: width 0.3s ease;
}

.batch-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.sku-checkbox-list {
  max-height: 160px;
  overflow-y: auto;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.sku-checkbox-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  cursor: pointer;
}
.empty-state {
  grid-column: 1 / -1;
  text-align: center;
  padding: 40px;
}
</style>
