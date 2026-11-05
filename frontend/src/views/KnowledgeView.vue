<template>
  <div class="knowledge-page">
    <div class="page-title-row">
      <div>
        <h1 class="page-title">企业品牌与合规知识库 (RAG)</h1>
        <p class="page-desc">基于 PostgreSQL 16 pgvector 1024 维向量引擎，支持品牌调性与海外广告法精准语义召回</p>
      </div>
      <div class="actions">
        <button class="btn btn-primary" @click="showModal = true">+ 录入品牌知识文档</button>
      </div>
    </div>

    <!-- 知识库与向量召回测试分栏 -->
    <div class="knowledge-grid">
      <!-- 左列：文档列表 -->
      <div class="card docs-card">
        <h3 class="card-title mb-3">知识库文档清单</h3>
        <div class="table-container">
          <table class="data-table">
            <thead>
              <tr>
                <th>分类</th>
                <th>文档名称</th>
                <th>向量化状态</th>
                <th>创建时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="d in docs" :key="d.id">
                <td><span class="badge badge-info">{{ d.category }}</span></td>
                <td><strong>{{ d.name }}</strong></td>
                <td><span class="badge badge-success">{{ d.vector_status }}</span></td>
                <td>{{ d.create_time ? new Date(d.create_time).toLocaleDateString() : '-' }}</td>
              </tr>
              <tr v-if="docs.length === 0">
                <td colspan="4" class="text-center text-muted p-4">暂无知识库文档</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 右列：RAG 向量相似度检索测试器 -->
      <div class="card rag-tester-card">
        <h3 class="card-title mb-2">⚡ pgvector 向量检索调试器</h3>
        <p class="text-sm text-muted mb-3">模拟 RequirementAnalyzer 智能体在策划前检索相关品牌与风控条例</p>
        <div class="form-group">
          <label class="form-label">检索输入 Prompt / 意图</label>
          <input type="text" v-model="queryText" class="form-input" placeholder="例如: 品牌对于违规词与调性的要求" />
        </div>
        <button class="btn btn-primary btn-sm" @click="testRecall" :disabled="recalling">
          {{ recalling ? '向量计算中...' : '🔍 执行余弦相似度召回' }}
        </button>

        <div v-if="recallResults.length" class="recall-box mt-3">
          <div class="recall-title">Top-K 语义召回分块 (pgvector):</div>
          <div v-for="(r, i) in recallResults" :key="i" class="recall-item mt-2">
            <span class="badge badge-info mb-1">{{ r.doc_type }}</span>
            <p class="text-sm">{{ r.content }}</p>
          </div>
        </div>
      </div>
    </div>

    <!-- 新建文档弹窗 -->
    <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
      <div class="modal-content">
        <h3 class="modal-title mb-4">录入新品牌/风控知识文档</h3>
        <div class="form-group">
          <label class="form-label">文档分类</label>
          <select v-model="form.category" class="form-select">
            <option value="brand">brand (品牌调性与主张)</option>
            <option value="compliance">compliance (合规政策与禁忌)</option>
            <option value="market">market (海外目标市场消费画像)</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">文档名称</label>
          <input type="text" v-model="form.name" class="form-input" placeholder="例如: 2026北美露营装备客群偏好规范" />
        </div>
        <div class="form-group">
          <label class="form-label">知识正文内容 (系统自动进行 1024 维切片向量化)</label>
          <textarea v-model="form.content" class="form-textarea" rows="4" placeholder="粘贴正文段落..."></textarea>
        </div>
        <div class="modal-footer mt-4">
          <button class="btn btn-secondary" @click="showModal = false">取消</button>
          <button class="btn btn-primary" @click="submitDoc">提交并构建向量索引</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import client from '@/api/client'

const docs = ref<any[]>([])
const showModal = ref(false)
const queryText = ref('品牌调性与绝对化用词禁忌')
const recalling = ref(false)
const recallResults = ref<any[]>([])

const form = ref({
  category: 'brand',
  doc_type: 'brand_guideline',
  name: '',
  content: ''
})

async function loadDocs() {
  try {
    const res = await client.get('/knowledge/docs')
    docs.value = res.data?.data?.items || []
  } catch (e) {
    console.error(e)
  }
}

async function submitDoc() {
  if (!form.value.name || !form.value.content) return
  try {
    await client.post('/knowledge/docs', form.value)
    showModal.value = false
    alert('文档录入成功，已完成 1024 维向量切片与索引！')
    loadDocs()
  } catch (e) {
    alert('录入失败')
  }
}

async function testRecall() {
  if (!queryText.value) return
  recalling.value = true
  try {
    const res = await client.post('/knowledge/query', {
      query_text: queryText.value,
      top_k: 2
    })
    recallResults.value = res.data?.data?.results || []
  } catch (e) {
    alert('检索异常')
  } finally {
    recalling.value = false
  }
}

onMounted(() => {
  loadDocs()
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

.knowledge-grid {
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 20px;
}

.recall-box {
  background: #f8fafc;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
}
.recall-title { font-size: 13px; font-weight: 600; color: #1e293b; }
.recall-item {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 10px;
}
.modal-footer { display: flex; justify-content: flex-end; gap: 12px; }
</style>
