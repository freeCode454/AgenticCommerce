<template>
  <div class="workbench-page">
    <!-- 顶部任务状态栏 -->
    <div class="workbench-header card">
      <div class="header-left">
        <router-link to="/tasks" class="back-link">← 返回任务列表</router-link>
        <div class="task-title-wrap">
          <h2 class="task-name">{{ taskData.sku_name || '智能体生成工作台' }}</h2>
          <span class="sku-tag">SKU: {{ taskData.sku_code || taskData.sku_id }}</span>
          <span :class="['badge', taskData.status === 'completed' ? 'badge-success' : 'badge-info']">
            {{ taskData.status }}
          </span>
        </div>
      </div>
      <div class="header-right">
        <button class="btn btn-secondary btn-sm" @click="fetchTaskDetail">🔄 刷新状态</button>
        <button class="btn btn-primary btn-sm" @click="retryWorkflow">⚡ 重新触发 P-E-V 流水线</button>
      </div>
    </div>

    <!-- 7-Agent DAG 实时交互拓扑图 -->
    <div class="dag-container card mt-4">
      <div class="dag-header">
        <h3 class="card-title">7-Agent 实时编排拓扑 (P-E-V 闭环工作流)</h3>
        <span class="dag-legend">点击节点可查看历史 Prompt 输入、输出快照与 Token 消耗</span>
      </div>

      <div class="dag-flow">
        <div 
          v-for="(node, idx) in agentNodes" 
          :key="node.key"
          :class="['dag-node', getNodeStatusClass(node.key), activeNodeKey === node.key ? 'node-selected' : '']"
          @click="selectNode(node.key)"
        >
          <div class="node-badge-idx">{{ idx + 1 }}</div>
          <div class="node-icon">{{ node.icon }}</div>
          <div class="node-info">
            <span class="node-label">{{ node.name }}</span>
            <span class="node-sub">{{ node.desc }}</span>
          </div>
          <span class="node-status-indicator"></span>
        </div>
      </div>
    </div>

    <!-- 节点运行明细抽屉 / 弹层 -->
    <div v-if="selectedNodeRun" class="node-detail-banner card mt-3">
      <div class="banner-header">
        <h4>⚡ 节点执行明细快照: {{ selectedNodeRun.node_name }}</h4>
        <button class="close-btn" @click="selectedNodeRun = null">✕</button>
      </div>
      <div class="banner-metrics">
        <span>执行耗时: <strong>{{ selectedNodeRun.elapsed_ms }} ms</strong></span>
        <span>消耗 Tokens: <strong>{{ (selectedNodeRun.prompt_tokens || 0) + (selectedNodeRun.completion_tokens || 0) }}</strong></span>
        <span>模型费用: <strong>${{ selectedNodeRun.cost }}</strong></span>
        <span>状态: <span class="badge badge-success">{{ selectedNodeRun.status }}</span></span>
      </div>
      <div class="banner-content mt-2">
        <pre class="json-code">{{ JSON.stringify(selectedNodeRun.output_data, null, 2) }}</pre>
      </div>
    </div>

    <!-- 生成物料产出区 (文案 + 图像 + 视频 + 质检) -->
    <div class="workspace-grid mt-4">
      <!-- 左列：出海高转化文案与合规质检 -->
      <div class="left-col">
        <!-- 文案卡片 -->
        <div class="card copy-card">
          <div class="card-header">
            <h3 class="card-title">✍️ 亚马逊标准高转化英文文案</h3>
            <button class="btn btn-secondary btn-sm" @click="copyAllText">复制全文</button>
          </div>

          <div v-if="copyData" class="copy-body">
            <div class="copy-field">
              <label class="field-label">Listing 核心大卖标题 (Title)</label>
              <div class="field-box">{{ copyData.title }}</div>
            </div>

            <div class="copy-field mt-3">
              <label class="field-label">五点描述 (Five Bullets)</label>
              <ul class="bullets-list">
                <li v-for="(b, i) in copyData.bullets" :key="i" class="bullet-item">
                  {{ b }}
                </li>
              </ul>
            </div>

            <div class="copy-field mt-3">
              <label class="field-label">SEO 搜索关键词 (Keywords)</label>
              <div class="keywords-wrap">
                <span v-for="(k, i) in copyData.keywords" :key="i" class="keyword-pill"># {{ k }}</span>
              </div>
            </div>
          </div>
          <div v-else class="empty-hint">文案智能体策划中...</div>
        </div>

        <!-- 质检报告卡片 -->
        <div class="card compliance-card mt-4">
          <div class="card-header">
            <h3 class="card-title">🛡️ 质检与合规评估报告 (Quality Review)</h3>
            <span v-if="complianceData" :class="['badge', complianceData.passed ? 'badge-success' : 'badge-danger']">
              {{ complianceData.passed ? '通过 (PASSED)' : '未通过 (RETRY)' }}
            </span>
          </div>

          <div v-if="complianceData" class="compliance-body">
            <div class="score-display">
              <div class="score-num">{{ complianceData.score }}</div>
              <div class="score-meta">
                <span class="score-title">综合合规质检得分</span>
                <span class="score-desc">达标线 85.0 分，低于阈值触发自动回退重试</span>
              </div>
            </div>

            <div class="dimensions-grid mt-3">
              <div v-for="(val, key) in complianceData.dimensions" :key="key" class="dim-box">
                <span class="dim-name">{{ key }}</span>
                <span class="dim-score">{{ val }}分</span>
              </div>
            </div>

            <div class="suggestions-box mt-3" v-if="complianceData.suggestions?.length">
              <div class="sugg-title">智能体优化建议:</div>
              <ul class="sugg-list">
                <li v-for="(s, idx) in complianceData.suggestions" :key="idx">{{ s }}</li>
              </ul>
            </div>
          </div>
          <div v-else class="empty-hint">等待审核智能体验收...</div>
        </div>
      </div>

      <!-- 右列：Wanx 视觉图像素材与 Kling 视频画廊 -->
      <div class="right-col">
        <!-- 图像素材 -->
        <div class="card assets-card">
          <div class="card-header">
            <h3 class="card-title">🎨 万相 2.1 多视角高清商品图 ({{ imageAssets.length }} 张)</h3>
          </div>
          <div class="image-gallery">
            <div v-for="img in imageAssets" :key="img.id" class="image-card">
              <img :src="img.url" :alt="img.sub_type" class="product-thumb" />
              <div class="image-overlay">
                <span class="image-tag">{{ img.sub_type }}</span>
                <a :href="img.url" target="_blank" class="zoom-btn">🔍 原图</a>
              </div>
            </div>
          </div>
        </div>

        <!-- 视频素材 -->
        <div class="card video-card mt-4">
          <div class="card-header">
            <h3 class="card-title">🎬 可灵 Kling AI 动态带货短视频</h3>
            <span v-if="videoAsset" class="badge badge-success">5秒 16:9 HD</span>
          </div>
          <div v-if="videoAsset" class="video-container">
            <video :src="videoAsset.url" controls class="video-player"></video>
            <div class="video-meta mt-2 text-sm text-muted">
              <span>模型: Kling-V1</span> |
              <span>用于独立站 / TikTok 商品卡展示</span>
            </div>
          </div>
          <div v-else class="empty-hint">视频智能体渲染中...</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import client from '@/api/client'

const route = useRoute()
const taskId = computed(() => (route.params.taskId as string) || '')

const taskData = ref<any>({})
const copyData = ref<any>(null)
const assetsData = ref<any[]>([])
const complianceData = ref<any>(null)
const nodeRuns = ref<any[]>([])
const activeNodeKey = ref<string>('')
const selectedNodeRun = ref<any>(null)

// 计时器相关
const runningElapsedMs = ref(0)
let timerInterval: any = null

let ws: WebSocket | null = null

const agentNodes = [
  { key: 'orchestrator', name: '总控调度', desc: '全局编排与SKU挂载', icon: '🧭' },
  { key: 'requirement_analyzer', name: '需求分析', desc: 'RAG知识与客群画像', icon: '🔍' },
  { key: 'creative_planner', name: '创意策划', desc: '高转化五点与标题', icon: '✍️' },
  { key: 'visual_designer', name: '视觉设计', desc: '分镜规划与Prompt拆解', icon: '📐' },
  { key: 'image_generator', name: '图片生成', desc: '万相2.1多视角生成', icon: '🎨' },
  { key: 'video_generator', name: '视频生成', desc: '可灵AI短视频渲染', icon: '🎬' },
  { key: 'quality_reviewer', name: '质量审核', desc: 'P-E-V闭环与合规打分', icon: '🛡️' },
]

const imageAssets = computed(() => assetsData.value.filter(a => a.type === 'image'))
const videoAsset = computed(() => assetsData.value.find(a => a.type === 'video'))

function getNodeStatusClass(nodeKey: string) {
  const run = nodeRuns.value.find(r => r.node_name === nodeKey)
  if (!run) return 'node-pending'
  return run.status === 'success' ? 'node-success' : 'node-running'
}

function selectNode(nodeKey: string) {
  activeNodeKey.value = nodeKey
  selectedNodeRun.value = nodeRuns.value.find(r => r.node_name === nodeKey) || null
}

async function fetchTaskDetail() {
  if (!taskId.value) return
  try {
    const res = await client.get(`/tasks/${taskId.value}`)
    const data = res.data?.data || {}
    taskData.value = data.task || {}
    copyData.value = data.copy
    assetsData.value = data.assets || []
    complianceData.value = data.compliance_report

    const nodesRes = await client.get(`/tasks/${taskId.value}/nodes`)
    nodeRuns.value = nodesRes.data?.data?.items || []
  } catch (e) {
    console.error('加载任务详情失败', e)
  }
}

async function retryWorkflow() {
  if (!taskId.value) return
  try {
    await client.post(`/tasks/${taskId.value}/run`)
    alert('已重新下发 7-Agent 工作流，系统正在后台流转！')
    setTimeout(fetchTaskDetail, 2000)
  } catch (e) {
    alert('重新下发失败')
  }
}

function copyAllText() {
  if (!copyData.value) return
  const fullText = `TITLE:\n${copyData.value.title}\n\nBULLETS:\n${copyData.value.bullets?.join('\n')}\n\nKEYWORDS:\n${copyData.value.keywords?.join(', ')}`
  navigator.clipboard.writeText(fullText)
  alert('文案已成功复制到剪贴板！')
}

// WebSocket 实时连接
function initWebSocket() {
  if (!taskId.value) return
  
  // 假设后端 ws 挂载在同样主机的 /ws/tasks/:taskId 上 (或走 vite proxy)
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  // 通过 VITE 代理或直接拼接
  const wsUrl = `${protocol}//${window.location.host}/api/v1/ws/tasks/${taskId.value}`
  
  ws = new WebSocket(wsUrl)
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      if (data.type === 'node_update') {
        const payload = data.payload
        // 更新或插入 nodeRuns
        const idx = nodeRuns.value.findIndex(r => r.node_name === payload.node_name)
        if (idx !== -1) {
          nodeRuns.value[idx] = { ...nodeRuns.value[idx], ...payload }
        } else {
          nodeRuns.value.push(payload)
        }
        
        // 如果当前展开的正好是这个节点，更新它
        if (activeNodeKey.value === payload.node_name) {
          selectedNodeRun.value = nodeRuns.value.find(r => r.node_name === payload.node_name)
        }
        
        // 当收到任务更新时，如果是资产生成完毕，刷新一次整体接口以拿到图片/文案
        if (payload.status === 'success') {
          fetchTaskDetail()
        }
      } else if (data.type === 'task_update') {
        if (data.payload.status) {
          taskData.value.status = data.payload.status
        }
        if (data.payload.current_node) {
          taskData.value.current_node = data.payload.current_node
        }
      }
    } catch(e) {
      console.error('解析 WS 消息失败', e)
    }
  }
  
  ws.onclose = () => {
    console.log('WS 连接已断开')
  }
}

// 本地计时器，为正在运行的节点累加耗时，给用户 "没有卡死" 的视觉反馈
function startTimer() {
  timerInterval = setInterval(() => {
    runningElapsedMs.value += 1000
    
    // 自动更新所有状态为 running 的节点耗时
    nodeRuns.value.forEach(r => {
      if (r.status === 'running') {
        if (!r.elapsed_ms) r.elapsed_ms = 0
        r.elapsed_ms += 1000
      }
    })
    
    if (selectedNodeRun.value && selectedNodeRun.value.status === 'running') {
      selectedNodeRun.value.elapsed_ms = (selectedNodeRun.value.elapsed_ms || 0)
    }
  }, 1000)
}

onMounted(() => {
  fetchTaskDetail()
  initWebSocket()
  startTimer()
})

onUnmounted(() => {
  if (ws) ws.close()
  if (timerInterval) clearInterval(timerInterval)
})
</script>

<style scoped>
.workbench-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
}
.back-link {
  font-size: 12px;
  color: var(--primary);
  text-decoration: none;
  font-weight: 500;
  display: block;
  margin-bottom: 4px;
}
.task-title-wrap {
  display: flex;
  align-items: center;
  gap: 12px;
}
.task-name {
  font-size: 18px;
  font-weight: 700;
}
.sku-tag {
  background: #f1f5f9;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  color: #475569;
}

.dag-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.dag-legend {
  font-size: 12px;
  color: var(--text-light);
}

.dag-flow {
  display: flex;
  align-items: center;
  gap: 12px;
  overflow-x: auto;
  padding-bottom: 8px;
}
.dag-node {
  flex: 1;
  min-width: 140px;
  background: #f8fafc;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 12px;
  position: relative;
  cursor: pointer;
  transition: all 0.2s ease;
}
.dag-node:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-sm);
}
.node-selected {
  border-color: var(--primary) !important;
  box-shadow: 0 0 0 2px var(--primary-glow) !important;
}
.node-badge-idx {
  position: absolute;
  top: 6px;
  right: 8px;
  font-size: 10px;
  font-weight: 700;
  color: var(--text-light);
}
.node-icon {
  font-size: 20px;
  margin-bottom: 4px;
}
.node-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-main);
}
.node-sub {
  font-size: 10.5px;
  color: var(--text-muted);
}
.node-success {
  border-color: #a7f3d0;
  background: #ecfdf5;
}
.node-running {
  border-color: #93c5fd;
  background: #eff6ff;
}
.node-pending {
  opacity: 0.6;
}

.node-detail-banner {
  background: #1e293b;
  color: #f8fafc;
  padding: 16px;
}
.banner-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.close-btn {
  background: none;
  border: none;
  color: #94a3b8;
  font-size: 16px;
  cursor: pointer;
}
.banner-metrics {
  display: flex;
  gap: 20px;
  font-size: 13px;
  margin-top: 8px;
  color: #cbd5e1;
}
.json-code {
  background: #0f172a;
  padding: 12px;
  border-radius: 6px;
  font-size: 12px;
  color: #38bdf8;
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.workspace-grid {
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 20px;
}

.field-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  margin-bottom: 4px;
  display: block;
}
.field-box {
  background: #f8fafc;
  padding: 10px 14px;
  border-radius: 6px;
  border: 1px solid var(--border);
  font-size: 14px;
  font-weight: 500;
}
.bullets-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.bullet-item {
  background: #f8fafc;
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid var(--border);
  font-size: 13px;
}
.keywords-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.keyword-pill {
  background: #eef2ff;
  color: var(--primary);
  font-size: 12px;
  padding: 3px 8px;
  border-radius: 4px;
  font-weight: 500;
}

.score-display {
  display: flex;
  align-items: center;
  gap: 16px;
  background: #ecfdf5;
  padding: 14px 18px;
  border-radius: 10px;
}
.score-num {
  font-size: 32px;
  font-weight: 800;
  color: #047857;
}
.score-title {
  font-size: 14px;
  font-weight: 600;
  color: #065f46;
  display: block;
}
.score-desc {
  font-size: 12px;
  color: #047857;
}
.dimensions-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}
.dim-box {
  display: flex;
  justify-content: space-between;
  padding: 8px 12px;
  background: #f8fafc;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 12.5px;
}
.dim-name { color: var(--text-muted); }
.dim-score { font-weight: 700; color: var(--primary); }

.sugg-title {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text-main);
  margin-bottom: 4px;
}
.sugg-list {
  font-size: 12.5px;
  color: #475569;
  padding-left: 18px;
}

.image-gallery {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-top: 12px;
}
.image-card {
  position: relative;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--border);
  aspect-ratio: 1;
}
.product-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.image-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: rgba(15, 23, 42, 0.7);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 8px;
}
.image-tag {
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
}
.zoom-btn {
  color: #38bdf8;
  font-size: 11px;
  text-decoration: none;
}

.video-container {
  margin-top: 12px;
}
.video-player {
  width: 100%;
  border-radius: 8px;
  background: #000;
  max-height: 240px;
}

.empty-hint {
  text-align: center;
  padding: 30px;
  color: var(--text-light);
  font-size: 13px;
}
</style>
