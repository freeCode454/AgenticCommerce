<template>
  <div class="listing-page">
    <div class="page-title-row">
      <div>
        <h1 class="page-title">跨境多平台刊登发布</h1>
        <p class="page-desc">将通过质检的完整商品物料一键同步推送到 Amazon、Shopify 与 TikTok Shop 线上店铺</p>
      </div>
      <div class="actions">
        <button class="btn btn-primary" @click="showModal = true">+ 发起跨平台刊登</button>
      </div>
    </div>

    <!-- 刊登历史记录 -->
    <div class="card">
      <div class="table-container">
        <table class="data-table">
          <thead>
            <tr>
              <th>刊登 ID</th>
              <th>商品 SKU</th>
              <th>目标平台</th>
              <th>外部平台商品 ID</th>
              <th>状态</th>
              <th>刊登时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="l in listings" :key="l.id">
              <td><code class="code-pill">{{ l.id }}</code></td>
              <td><strong>{{ l.sku_name }}</strong></td>
              <td><span class="badge badge-info">{{ l.platform.toUpperCase() }}</span></td>
              <td><code>{{ l.listing_data?.external_product_id || '-' }}</code></td>
              <td><span class="badge badge-success">{{ l.status }}</span></td>
              <td>{{ l.create_time ? new Date(l.create_time).toLocaleString() : '-' }}</td>
            </tr>
            <tr v-if="listings.length === 0">
              <td colspan="6" class="text-center text-muted p-4">暂无刊登记录，可点击右上角发起商品上架</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 刊登弹窗 -->
    <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
      <div class="modal-content">
        <h3 class="modal-title mb-4">发起跨平台刊登上架</h3>
        <div class="form-group">
          <label class="form-label">选择要上架的商品 SKU</label>
          <select v-model="selectedSkuId" class="form-select">
            <option v-for="s in skus" :key="s.id" :value="s.id">
              [{{ s.code }}] {{ s.name }}
            </option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">目标刊登平台</label>
          <select v-model="targetPlatform" class="form-select">
            <option value="amazon">Amazon 亚马逊北美站</option>
            <option value="shopify">Shopify 品牌独立站</option>
            <option value="tiktok">TikTok Shop 美区小店</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">建议零售价 (USD)</label>
          <input type="text" v-model="price" class="form-input" placeholder="49.99" />
        </div>
        <div class="modal-footer mt-4">
          <button class="btn btn-secondary" @click="showModal = false">取消</button>
          <button class="btn btn-primary" @click="submitListing" :disabled="submitting">
            {{ submitting ? '同步中...' : '立即同步刊登' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import client from '@/api/client'

const listings = ref<any[]>([])
const skus = ref<any[]>([])
const showModal = ref(false)
const selectedSkuId = ref('')
const targetPlatform = ref('amazon')
const price = ref('49.99')
const submitting = ref(false)

async function loadListings() {
  try {
    const res = await client.get('/listings')
    listings.value = res.data?.data?.items || []
  } catch (e) {
    console.error(e)
  }
}

async function loadSkus() {
  try {
    const res = await client.get('/skus')
    skus.value = res.data?.data?.items || []
    if (skus.value.length) selectedSkuId.value = skus.value[0].id
  } catch (e) {
    console.error(e)
  }
}

async function submitListing() {
  if (!selectedSkuId.value) return
  submitting.value = true
  try {
    await client.post('/listings', {
      sku_id: selectedSkuId.value,
      platform: targetPlatform.value,
      listing_data: { price: price.value }
    })
    showModal.value = false
    alert(`商品已成功同步刊登至 ${targetPlatform.value}！`)
    loadListings()
  } catch (e) {
    alert('刊登失败')
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  loadListings()
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
.modal-footer { display: flex; justify-content: flex-end; gap: 12px; }
.code-pill { background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 12px; }
</style>
