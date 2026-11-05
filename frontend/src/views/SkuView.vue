<template>
  <div class="sku-page">
    <div class="page-title-row">
      <div>
        <h1 class="page-title">商品 SKU 资产库</h1>
        <p class="page-desc">维护出海选品基础规格、特征卖点与设计参考图</p>
      </div>
      <div class="actions">
        <button class="btn btn-primary" @click="openCreateModal">+ 录入新商品 SKU</button>
      </div>
    </div>

    <!-- 筛选工具栏 -->
    <div class="card filter-bar mb-4">
      <div class="filter-group">
        <label>关键词搜索:</label>
        <input type="text" v-model="searchQ" class="form-input" placeholder="输入编码或名称" @keyup.enter="loadSkus" />
      </div>
      <div class="filter-group">
        <label>类目分类:</label>
        <select v-model="selectedCategory" class="form-select" @change="loadSkus">
          <option value="">全部类目</option>
          <option value="户外运动">户外运动</option>
          <option value="数码配件">数码配件</option>
          <option value="家居生活">家居生活</option>
        </select>
      </div>
      <button class="btn btn-secondary btn-sm" @click="loadSkus">搜索过滤</button>
    </div>

    <!-- SKU 卡片栅格 -->
    <div class="sku-grid">
      <div v-for="s in skus" :key="s.id" class="sku-card card">
        <div class="sku-media">
          <img :src="s.images?.[0] || '/bg_img/outdoor.jpg'" class="sku-img" />
          <span class="category-tag">{{ s.category }}</span>
        </div>
        <div class="sku-content">
          <div class="sku-code-row">
            <code class="code-pill">{{ s.code }}</code>
          </div>
          <h3 class="sku-title">{{ s.name }}</h3>
          <p class="sku-desc">{{ s.description }}</p>

          <div class="specs-box mt-2">
            <div v-for="(v, k) in s.specs" :key="k" class="spec-row">
              <span class="spec-k">{{ k }}:</span>
              <span class="spec-v">{{ v }}</span>
            </div>
          </div>
        </div>
        <div class="sku-card-actions mt-3">
          <button class="btn btn-primary btn-sm full-width" @click="generateForSku(s.id)">⚡ 发起 7-Agent 生成</button>
        </div>
      </div>
    </div>

    <!-- 录入新 SKU 弹窗 -->
    <div v-if="showCreateModal" class="modal-overlay" @click.self="showCreateModal = false">
      <div class="modal-content modal-lg">
        <h3 class="modal-title mb-4">录入新商品 SKU</h3>

        <div class="form-group">
          <label class="form-label">商品编码 (SKU Code)</label>
          <div style="display: flex; gap: 8px;">
            <input type="text" v-model="form.code" class="form-input" placeholder="例如: OUT-12345" />
            <button type="button" class="btn btn-secondary" style="white-space: nowrap; padding: 0 16px;" @click="generateSku">自动生成</button>
          </div>
        </div>
        
        <div class="form-group">
          <label class="form-label">商品名称</label>
          <input type="text" v-model="form.name" class="form-input" placeholder="例如: 极简防风双人户外露营帐篷" />
        </div>

        <div class="form-group">
          <label class="form-label">类目分类</label>
          <select v-model="form.category" class="form-select" @change="onCategoryChange">
            <option value="户外运动">户外运动</option>
            <option value="数码配件">数码配件</option>
            <option value="家居生活">家居生活</option>
          </select>
        </div>

        <div class="form-group">
          <div class="label-with-action">
            <label class="form-label mb-0">商品描述与白话卖点</label>
            <button 
              type="button" 
              class="btn btn-xs btn-ai-extract" 
              :disabled="isExtracting"
              @click="aiExtractSpecs" 
              title="发送至通义千问 Qwen 大模型自动提取 JSON 参数"
            >
              {{ isExtracting ? '⚡ 正在调用通义千问提取中...' : '⚡ 大模型智能提取规格' }}
            </button>
          </div>
          <textarea 
            v-model="form.description" 
            class="form-textarea" 
            rows="3" 
            placeholder="如：这是一款最新研发的降噪耳机，蓝牙5.4芯片，防水达到IPX5级，电池500mAh，重210g..."
          ></textarea>
        </div>

        <!-- 商品详细规格参数编辑器 -->
        <div class="form-group specs-editor-card">
          <div class="specs-editor-header">
            <div>
              <span class="specs-title">
                商品详细规格参数 
                <span v-if="specList.length > 0" class="specs-count">({{ specList.length }} 项)</span>
              </span>
              <span class="specs-subtitle">配置产品核心特征（如材质、尺寸、功能指标），便于自动渲染商品详情表与素材特征</span>
            </div>
            <div class="specs-actions">
              <button type="button" class="btn btn-xs btn-outline" @click="loadCategoryPresetSpecs">
                📋 载入【{{ form.category }}】预设参数
              </button>
              <button type="button" class="btn btn-xs btn-secondary" @click="addSpecRow">
                + 新增属性键值
              </button>
            </div>
          </div>

          <div class="specs-input-list">
            <div v-for="(item, idx) in specList" :key="idx" class="spec-input-row">
              <input type="text" v-model="item.key" class="form-input key-input" placeholder="参数名称 (如: 蓝牙版本)" />
              <span class="colon">:</span>
              <input type="text" v-model="item.value" class="form-input val-input" placeholder="参数数值 (如: 5.4)" />
              <button type="button" class="btn-icon-del" title="删除" @click="removeSpecRow(idx)">✕</button>
            </div>
            <div v-if="specList.length === 0" class="empty-specs-tip">
              暂未配置规格参数，可点击右上角【+ 新增属性键值】无限扩展添加
            </div>
          </div>
        </div>

        <div class="modal-footer mt-4">
          <button class="btn btn-secondary" @click="showCreateModal = false" :disabled="isSubmitting">取消</button>
          <button class="btn btn-primary" @click="submitCreateSku" :disabled="isSubmitting">
            <template v-if="isSubmitting">
              <span class="spinner"></span> 正在保存与提取规格...
            </template>
            <template v-else>
              保存入库
            </template>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import client from '@/api/client'

const router = useRouter()
const skus = ref<any[]>([])
const searchQ = ref('')
const selectedCategory = ref('')
const showCreateModal = ref(false)
const isExtracting = ref(false)

interface SpecItem {
  key: string
  value: string
}

const specList = ref<SpecItem[]>([])

const form = ref({
  code: '',
  name: '',
  category: '户外运动',
  description: '',
  images: []
})

// 类目通用规格模版预设
const CATEGORY_PRESETS: Record<string, SpecItem[]> = {
  '户外运动': [
    { key: '材质', value: '高强度防水撕裂布' },
    { key: '重量', value: '1.5kg' },
    { key: '防风等级', value: '7级' },
    { key: '展开尺寸', value: '200x150x110cm' }
  ],
  '数码配件': [
    { key: '蓝牙版本', value: '5.4' },
    { key: '防水等级', value: 'IPX5' },
    { key: '电池容量', value: '500mAh' },
    { key: '降噪深度', value: '45dB' }
  ],
  '家居生活': [
    { key: '材质', value: '天然环保大理石/竹木' },
    { key: '适用空间', value: '客厅/卧室' },
    { key: '容量', value: '1.2L' },
    { key: '净重', value: '850g' }
  ]
}

function openCreateModal() {
  resetForm()
  showCreateModal.value = true
}

function onCategoryChange() {
  if (specList.value.length === 0 || specList.value.every(s => !s.key && !s.value)) {
    loadCategoryPresetSpecs()
  }
}

function loadCategoryPresetSpecs() {
  const preset = CATEGORY_PRESETS[form.value.category] || []
  specList.value = preset.map(item => ({ ...item }))
}

function addSpecRow() {
  specList.value.push({ key: '', value: '' })
}

function removeSpecRow(index: number) {
  specList.value.splice(index, 1)
}

function generateSku() {
  const categoryCodeMap: Record<string, string> = {
    '户外运动': 'OUT',
    '数码配件': 'DGC',
    '家居生活': 'HOM'
  }
  const prefix = categoryCodeMap[form.value.category] || 'GEN'
  const randomNum = Math.floor(Math.random() * 90000) + 10000
  form.value.code = `${prefix}-${randomNum}`
}

// 真正调用后端 API 通义千问 Qwen 大模型提取白话中的规格属性
async function aiExtractSpecs() {
  const desc = form.value.description
  if (!desc.trim()) {
    alert('请先在上方输入商品白话描述！')
    return
  }

  isExtracting.value = true
  try {
    const res = await client.post('/skus/extract-specs', { description: desc })
    const specsData = res.data?.data
    const isMock = res.data?.is_mock ? ' (Mock模式)' : ' (通义千问 Qwen)'

    if (specsData && typeof specsData === 'object' && Object.keys(specsData).length > 0) {
      const extracted: SpecItem[] = Object.entries(specsData).map(([k, v]) => ({
        key: String(k),
        value: String(v)
      }))
      specList.value = extracted
      alert(`⚡ 通义千问 Qwen 大模型提取成功${isMock}！已结构化解析出 ${extracted.length} 项规格参数，可自由核对或微调。`)
    } else {
      alert('大模型已响应，未从描述中提取出明确的规格属性，可手动点击【+ 新增属性键值】。')
      if (specList.value.length === 0) {
        addSpecRow()
      }
    }
  } catch (e: any) {
    alert('调用大模型接口失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    isExtracting.value = false
  }
}

async function loadSkus() {
  try {
    let url = '/skus?page=1&page_size=50'
    if (searchQ.value) url += `&q=${searchQ.value}`
    if (selectedCategory.value) url += `&category=${selectedCategory.value}`
    const res = await client.get(url)
    skus.value = res.data?.data?.items || []
  } catch (e) {
    console.error(e)
  }
}

function resetForm() {
  form.value = {
    code: '',
    name: '',
    category: '户外运动',
    description: '',
    images: []
  }
  loadCategoryPresetSpecs()
}

const isSubmitting = ref(false)

async function submitCreateSku() {
  if (!form.value.code || !form.value.name) {
    alert('请填写编码与商品名称')
    return
  }

  const specsDict: Record<string, string> = {}
  specList.value.forEach(item => {
    if (item.key.trim() && item.value.trim()) {
      specsDict[item.key.trim()] = item.value.trim()
    }
  })

  // 如果用户写了描述但没写参数，后台会自动触发大模型，这里给个友好的 UI 提示等待
  if (Object.keys(specsDict).length === 0 && form.value.description.trim()) {
    console.log('用户未填规格但填写了描述，后台将自动兜底触发 Qwen 大模型提取...')
  }

  isSubmitting.value = true
  try {
    const imgMap: Record<string, string> = {
      '户外运动': '/bg_img/outdoor.jpg',
      '数码配件': '/bg_img/digital.jpg',
      '家居生活': '/bg_img/home.jpg'
    }
    const payload = { 
      ...form.value, 
      specs: specsDict,
      images: [imgMap[form.value.category] || '/bg_img/outdoor.jpg'] 
    }

    await client.post('/skus', payload)
    showCreateModal.value = false
    resetForm()
    alert('SKU 创建成功！参数已自动入库。')
    loadSkus()
  } catch (e: any) {
    alert(e.response?.data?.detail || '创建失败，编码可能已存在')
  } finally {
    isSubmitting.value = false
  }
}

async function generateForSku(skuId: string) {
  try {
    const res = await client.post('/tasks', {
      sku_id: skuId,
      config: { platform: 'amazon', language: 'en', max_retries: 2 }
    })
    const taskId = res.data?.data?.task_id
    alert('任务已发起，正在转入 7-Agent 工作台！')
    router.push(`/workbench/${taskId}`)
  } catch (e) {
    alert('发起失败')
  }
}

onMounted(() => {
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
  font-size: 13px;
}

.sku-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}
.sku-card {
  display: flex;
  flex-direction: column;
  padding: 0;
  overflow: hidden;
}
.sku-media {
  position: relative;
  height: 180px;
  overflow: hidden;
}
.sku-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.category-tag {
  position: absolute;
  top: 10px;
  right: 10px;
  background: rgba(15, 23, 42, 0.75);
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
}
.sku-content {
  padding: 16px;
  flex: 1;
}
.sku-code-row { margin-bottom: 6px; }
.code-pill { background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 11.5px; }
.sku-title { font-size: 15px; font-weight: 600; margin-bottom: 6px; }
.sku-desc { font-size: 12px; color: var(--text-muted); line-height: 1.4; max-height: 38px; overflow: hidden; }

.specs-box {
  background: #f8fafc;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px 10px;
  font-size: 11.5px;
}
.spec-row { display: flex; justify-content: space-between; margin-bottom: 2px; }
.spec-k { color: var(--text-light); }
.spec-v { font-weight: 500; }

.sku-card-actions { padding: 0 16px 16px; }
.full-width { width: 100%; }

/* 扩展规格参数编辑器样式 */
.modal-lg { max-width: 620px; }
.label-with-action {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.btn-ai-extract {
  background: #eff6ff;
  color: #2563eb;
  border: 1px solid #bfdbfe;
  font-size: 11.5px;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.btn-ai-extract:hover {
  background: #dbeafe;
  color: #1d4ed8;
}

.specs-editor-card {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px 14px;
  margin-top: 14px;
}
.specs-editor-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 10px;
}
.specs-title {
  display: block;
  font-size: 13.5px;
  font-weight: 600;
  color: #1e293b;
}
.specs-count {
  font-size: 12px;
  color: #3b82f6;
  font-weight: 600;
  margin-left: 2px;
}
.specs-subtitle {
  display: block;
  font-size: 11px;
  color: #64748b;
  margin-top: 2px;
}
.specs-actions {
  display: flex;
  gap: 8px;
}
.btn-outline {
  border: 1px solid #cbd5e1;
  background: #ffffff;
  color: #475569;
}
.btn-outline:hover {
  background: #f1f5f9;
}

.specs-input-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 300px;
  overflow-y: auto;
  padding-right: 6px;
}
.specs-input-list::-webkit-scrollbar {
  width: 5px;
}
.specs-input-list::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 4px;
}
.spec-input-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.key-input {
  width: 40%;
  font-size: 12.5px;
}
.colon {
  font-weight: bold;
  color: #94a3b8;
}
.val-input {
  flex: 1;
  font-size: 12.5px;
}
.btn-icon-del {
  background: transparent;
  border: none;
  color: #ef4444;
  font-size: 14px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
}
.btn-icon-del:hover {
  background: #fee2e2;
}
.empty-specs-tip {
  font-size: 12px;
  color: #94a3b8;
  text-align: center;
  padding: 12px 0;
}

.modal-footer { display: flex; justify-content: flex-end; gap: 12px; }
</style>

