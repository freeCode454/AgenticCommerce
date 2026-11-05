<template>
  <div class="provider-page">
    <div class="page-title-row">
      <div>
        <h1 class="page-title">AI 大模型厂商与 Key 配置</h1>
        <p class="page-desc">平台已打通阿里千问 (LLM)、通义万相 2.1 (生图) 与快手可灵 (生视频) 官方 API，支持真实 Key 配置与自动 Mock 容灾</p>
      </div>
    </div>

    <!-- 厂商卡片列表 -->
    <div class="providers-grid">
      <div v-for="p in providers" :key="p.id" class="provider-card card">
        <div class="provider-top">
          <div class="prov-brand">
            <span class="prov-icon">{{ getIcon(p.type) }}</span>
            <div>
              <h3 class="prov-name">{{ p.name }}</h3>
              <span class="badge badge-info">{{ p.type.toUpperCase() }}</span>
            </div>
          </div>
          <span :class="['badge', p.has_key ? 'badge-success' : 'badge-warning']">
            {{ p.has_key ? '真实 Key 已配置' : '高保真 Mock 模式' }}
          </span>
        </div>

        <div class="prov-body mt-3">
          <div class="info-row">
            <span class="info-k">API Key:</span>
            <code class="info-v">{{ p.api_key_masked }}</code>
          </div>
          <div class="info-row mt-1">
            <span class="info-k">默认模型:</span>
            <span class="info-v">{{ p.config?.model || '-' }}</span>
          </div>
          <div class="info-row mt-1">
            <span class="info-k">官方接入:</span>
            <a :href="getDocUrl(p.type)" target="_blank" class="doc-link">查看官方调用规范 ↗</a>
          </div>
        </div>

        <div class="prov-actions mt-4">
          <button class="btn btn-secondary btn-sm" @click="testProvider(p.id)" :disabled="testingId === p.id">
            {{ testingId === p.id ? '测试中...' : '📡 连通性测试' }}
          </button>
          <button class="btn btn-primary btn-sm" @click="openKeyModal(p)">🔑 配置 API Key</button>
        </div>
      </div>
    </div>

    <!-- 配置 Key 弹窗 -->
    <div v-if="editingProv" class="modal-overlay" @click.self="editingProv = null">
      <div class="modal-content">
        <h3 class="modal-title mb-3">配置 {{ editingProv.name }} API 凭证</h3>
        <p class="text-sm text-muted mb-4">
          密钥将采用安全加密后存储于数据库。配置真实 Key 后，7-Agent 将直接调度大模型线上生产算力。
        </p>

        <div class="form-group">
          <label class="form-label">输入 API Key (或留空使用 Mock 模式)</label>
          <input type="password" v-model="keyInput" class="form-input" placeholder="sk-xxxxxxxxxxxxxxxxxxxxxxxx" />
        </div>

        <div class="modal-footer mt-4">
          <button class="btn btn-secondary" @click="editingProv = null">取消</button>
          <button class="btn btn-primary" @click="saveKey">保存配置</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import client from '@/api/client'

const providers = ref<any[]>([])
const editingProv = ref<any>(null)
const keyInput = ref('')
const testingId = ref<string | null>(null)

function getIcon(type: string) {
  if (type === 'llm') return '🧠'
  if (type === 'image') return '🎨'
  return '🎬'
}

function getDocUrl(type: string) {
  if (type === 'llm') return 'https://help.aliyun.com/zh/model-studio/developer-reference/use-qwen-by-calling-api'
  if (type === 'image') return 'https://help.aliyun.com/zh/model-studio/developer-reference/wanx-api'
  return 'https://klingai.com/api/docs'
}

async function loadProviders() {
  try {
    const res = await client.get('/providers')
    providers.value = res.data?.data?.items || []
  } catch (e) {
    console.error(e)
  }
}

async function testProvider(provId: string) {
  testingId.value = provId
  try {
    const res = await client.post(`/providers/${provId}/test`)
    const data = res.data?.data
    alert(`测试结果: ${res.data?.message}\n运行模式: ${data?.mode}\n响应耗时: ${data?.latency_ms || 300} ms`)
  } catch (e) {
    alert('连通性测试异常')
  } finally {
    testingId.value = null
  }
}

function openKeyModal(prov: any) {
  editingProv.value = prov
  keyInput.value = ''
}

async function saveKey() {
  if (!editingProv.value) return
  try {
    await client.put(`/providers/${editingProv.value.id}`, {
      api_key: keyInput.value
    })
    editingProv.value = null
    alert('API Key 配置更新成功！')
    loadProviders()
  } catch (e) {
    alert('更新失败')
  }
}

onMounted(() => {
  loadProviders()
})
</script>

<style scoped>
.page-title-row { margin-bottom: 24px; }
.page-title { font-size: 22px; font-weight: 700; }
.page-desc { font-size: 13px; color: var(--text-muted); margin-top: 4px; }

.providers-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}
.provider-card { padding: 20px; }
.provider-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}
.prov-brand { display: flex; align-items: center; gap: 12px; }
.prov-icon { font-size: 26px; }
.prov-name { font-size: 16px; font-weight: 700; }

.info-row {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
}
.info-k { color: var(--text-muted); }
.info-v { font-weight: 500; }
.doc-link { color: var(--primary); text-decoration: none; font-size: 12px; font-weight: 600; }

.prov-actions {
  display: flex;
  gap: 10px;
}
.prov-actions button { flex: 1; }

.modal-footer { display: flex; justify-content: flex-end; gap: 12px; }
</style>
