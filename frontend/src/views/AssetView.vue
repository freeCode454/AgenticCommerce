<template>
  <div class="asset-page">
    <div class="page-title-row">
      <div>
        <h1 class="page-title">媒体素材资产库</h1>
        <p class="page-desc">汇集通义万相 2.1 高清多视角图片与快手可灵 AI 动态带货短视频</p>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="card filter-bar mb-4">
      <div class="filter-group">
        <label>素材类型:</label>
        <select v-model="filterType" class="form-select" @change="loadAssets">
          <option value="">全部类型</option>
          <option value="image">静态图片 (Images)</option>
          <option value="video">动态短视频 (Videos)</option>
        </select>
      </div>
      <div class="filter-group">
        <label>拍摄视角:</label>
        <select v-model="filterSubType" class="form-select" @change="loadAssets">
          <option value="">全部视角</option>
          <option value="main">白底主图 (Main)</option>
          <option value="scene">场景图 (Scene)</option>
          <option value="detail">细节图 (Detail)</option>
        </select>
      </div>
      <button class="btn btn-secondary btn-sm" @click="loadAssets">筛选刷新</button>
    </div>

    <!-- 资产网格 -->
    <div class="asset-grid">
      <div v-for="a in assets" :key="a.id" class="asset-item card">
        <div class="asset-preview">
          <img v-if="a.type === 'image'" :src="a.url" class="asset-media" />
          <video v-else-if="a.type === 'video'" :src="a.url" controls class="asset-media"></video>
          <span class="type-badge">{{ a.sub_type || a.type }}</span>
        </div>
        <div class="asset-info mt-2">
          <div class="sku-name"><strong>{{ a.sku_name }}</strong></div>
          <div class="text-xs text-muted">ID: {{ a.id }}</div>
          <div class="asset-meta-row mt-2">
            <span class="badge badge-info">{{ a.meta?.size || a.meta?.model || 'HD' }}</span>
            <span v-if="a.is_mock" class="badge badge-warning">Mock演示</span>
            <span v-else class="badge badge-success">真实AI生成</span>
            <a :href="a.url" target="_blank" class="download-link">下载素材 ↓</a>
          </div>
        </div>
      </div>

      <div v-if="assets.length === 0" class="empty-state card">
        暂无匹配素材资产
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import client from '@/api/client'

const assets = ref<any[]>([])
const filterType = ref('')
const filterSubType = ref('')

async function loadAssets() {
  try {
    let url = '/assets?page=1&page_size=50'
    if (filterType.value) url += `&type=${filterType.value}`
    if (filterSubType.value) url += `&sub_type=${filterSubType.value}`
    const res = await client.get(url)
    assets.value = res.data?.data?.items || []
  } catch (e) {
    console.error(e)
  }
}

onMounted(() => {
  loadAssets()
})
</script>

<style scoped>
.page-title-row { margin-bottom: 24px; }
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

.asset-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 18px;
}
.asset-item {
  padding: 12px;
  display: flex;
  flex-direction: column;
}
.asset-preview {
  position: relative;
  aspect-ratio: 1;
  background: #000;
  border-radius: 8px;
  overflow: hidden;
}
.asset-media {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.type-badge {
  position: absolute;
  top: 8px;
  left: 8px;
  background: rgba(15, 23, 42, 0.75);
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
  text-transform: uppercase;
}

.sku-name { font-size: 13.5px; }
.text-xs { font-size: 11px; }
.asset-meta-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
}
.download-link {
  color: var(--primary);
  text-decoration: none;
  font-weight: 600;
}
.empty-state {
  grid-column: 1 / -1;
  text-align: center;
  padding: 40px;
  color: var(--text-muted);
}
</style>
