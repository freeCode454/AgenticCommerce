<template>
  <div class="copy-page">
    <div class="page-title-row">
      <div>
        <h1 class="page-title">出海高转化文案库</h1>
        <p class="page-desc">沉淀 7-Agent 策划智能体产出的全套 Listing 标题、五点描述与长文案</p>
      </div>
    </div>

    <!-- 文案卡片瀑布流 -->
    <div class="copy-list">
      <div v-for="c in copies" :key="c.id" class="card copy-card mb-4">
        <div class="card-header">
          <div class="header-left">
            <span class="badge badge-info">{{ c.language.toUpperCase() }}</span>
            <span class="sku-tag">SKU: {{ c.sku_name }} ({{ c.sku_code }})</span>
            <span class="text-xs text-muted">任务: {{ c.task_id }}</span>
          </div>
          <div class="header-right">
            <button class="btn btn-secondary btn-sm" @click="copyText(c)">📋 复制全文</button>
            <button class="btn btn-primary btn-sm" @click="openEditModal(c)">✏️ 在线微调</button>
          </div>
        </div>

        <div class="copy-section mt-3">
          <label class="section-label">Listing 核心大卖标题</label>
          <div class="title-text">{{ c.title }}</div>
        </div>

        <div class="copy-section mt-3">
          <label class="section-label">五点描述 (Bullets)</label>
          <ul class="bullets-box">
            <li v-for="(b, idx) in c.bullets" :key="idx" class="bullet-item">{{ b }}</li>
          </ul>
        </div>

        <div class="copy-section mt-3">
          <label class="section-label">SEO 搜索关键词</label>
          <div class="keywords-wrap">
            <span v-for="(k, idx) in c.keywords" :key="idx" class="keyword-tag"># {{ k }}</span>
          </div>
        </div>
      </div>

      <div v-if="copies.length === 0" class="card text-center p-5 text-muted">
        暂无已生成文案，请前往工作台或任务列表发起生成
      </div>
    </div>

    <!-- 编辑文案弹窗 -->
    <div v-if="editingCopy" class="modal-overlay" @click.self="editingCopy = null">
      <div class="modal-content modal-lg">
        <h3 class="modal-title mb-4">人工在线微调文案</h3>
        <div class="form-group">
          <label class="form-label">标题 (Title)</label>
          <input type="text" v-model="editForm.title" class="form-input" />
        </div>
        <div class="form-group">
          <label class="form-label">五点描述 (每行一条)</label>
          <textarea v-model="editFormBulletsText" class="form-textarea" rows="5"></textarea>
        </div>
        <div class="modal-footer mt-4">
          <button class="btn btn-secondary" @click="editingCopy = null">取消</button>
          <button class="btn btn-primary" @click="saveEditedCopy">保存覆写</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import client from '@/api/client'

const copies = ref<any[]>([])
const editingCopy = ref<any>(null)
const editForm = ref({ title: '' })
const editFormBulletsText = ref('')

async function loadCopies() {
  try {
    const res = await client.get('/copies?page=1&page_size=30')
    copies.value = res.data?.data?.items || []
  } catch (e) {
    console.error(e)
  }
}

function copyText(c: any) {
  const text = `TITLE:\n${c.title}\n\nBULLETS:\n${c.bullets?.join('\n')}\n\nKEYWORDS:\n${c.keywords?.join(', ')}`
  navigator.clipboard.writeText(text)
  alert('文案已复制到剪贴板！')
}

function openEditModal(c: any) {
  editingCopy.value = c
  editForm.value.title = c.title
  editFormBulletsText.value = (c.bullets || []).join('\n')
}

async function saveEditedCopy() {
  if (!editingCopy.value) return
  const bullets = editFormBulletsText.value.split('\n').filter(b => b.trim())
  try {
    await client.put(`/copies/${editingCopy.value.id}`, {
      title: editForm.value.title,
      bullets: bullets
    })
    editingCopy.value = null
    alert('文案保存成功！')
    loadCopies()
  } catch (e) {
    alert('保存失败')
  }
}

onMounted(() => {
  loadCopies()
})
</script>

<style scoped>
.page-title-row { margin-bottom: 24px; }
.page-title { font-size: 22px; font-weight: 700; }
.page-desc { font-size: 13px; color: var(--text-muted); margin-top: 4px; }

.copy-card { padding: 20px; }
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--border);
  padding-bottom: 12px;
}
.header-left { display: flex; align-items: center; gap: 10px; }
.sku-tag { font-size: 12.5px; font-weight: 600; color: #334155; }
.text-xs { font-size: 11px; }

.section-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  display: block;
  margin-bottom: 4px;
}
.title-text {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-main);
  background: #f8fafc;
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid var(--border);
}
.bullets-box {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.bullet-item {
  background: #f8fafc;
  padding: 6px 12px;
  border-radius: 6px;
  border: 1px solid var(--border);
  font-size: 13px;
}
.keywords-wrap { display: flex; flex-wrap: wrap; gap: 6px; }
.keyword-tag {
  background: #eef2ff;
  color: var(--primary);
  font-size: 12px;
  padding: 3px 8px;
  border-radius: 4px;
}

.modal-lg { max-width: 680px; }
.modal-footer { display: flex; justify-content: flex-end; gap: 12px; }
.mb-4 { margin-bottom: 16px; }
</style>
