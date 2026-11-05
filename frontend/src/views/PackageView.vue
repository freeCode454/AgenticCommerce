<template>
  <div class="package-page">
    <div class="page-title-row">
      <div>
        <h1 class="page-title">物料交付打包与下载</h1>
        <p class="page-desc">一键将通过质检审核的文案、全套高精图片、带货视频与合规证明打包为 ZIP 归档</p>
      </div>
    </div>

    <!-- 可打包任务列表 -->
    <div class="package-grid">
      <div v-for="p in packages" :key="p.task_id" class="package-card card">
        <div class="card-header">
          <div>
            <h3 class="pkg-title">🎁 {{ p.package_name }}</h3>
            <span class="text-xs text-muted">关联商品: {{ p.sku_name }} ({{ p.sku_code }})</span>
          </div>
          <span class="badge badge-success">READY</span>
        </div>

        <div class="pkg-body mt-3">
          <p class="text-sm text-muted">
            包含: Amazon 5 Bullets 英文文案、3张 1024*1024 高精多视角图、5秒动态视频、合规评分证明。
          </p>
        </div>

        <div class="pkg-footer mt-4">
          <span class="text-xs text-muted">生成时间: {{ p.create_time ? new Date(p.create_time).toLocaleString() : '-' }}</span>
          <button class="btn btn-primary btn-sm" @click="downloadPackage(p.task_id)">⬇️ 一键下载交付物料包</button>
        </div>
      </div>

      <div v-if="packages.length === 0" class="card text-center p-5 text-muted">
        暂无已完成的物料包，任务经质检通过后将自动呈现在此
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import client from '@/api/client'

const packages = ref<any[]>([])

async function loadPackages() {
  try {
    const res = await client.get('/packages')
    packages.value = res.data?.data?.items || []
  } catch (e) {
    console.error(e)
  }
}

async function downloadPackage(taskId: string) {
  try {
    const res = await client.post('/packages/export', { task_id: taskId })
    const data = res.data?.data
    alert(`交付物料包打包就绪！\n包含: ${data?.media_assets?.length} 个媒体素材与文案\n下载链接: ${data?.download_archive_url}`)
  } catch (e) {
    alert('打包失败')
  }
}

onMounted(() => {
  loadPackages()
})
</script>

<style scoped>
.page-title-row { margin-bottom: 24px; }
.page-title { font-size: 22px; font-weight: 700; }
.page-desc { font-size: 13px; color: var(--text-muted); margin-top: 4px; }

.package-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 18px;
}
.package-card { padding: 20px; }
.pkg-title { font-size: 16px; font-weight: 600; }
.pkg-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
