<script setup lang="ts">
import { ref } from 'vue'
import { useCollection } from '@/composables/useCollection'
import { dateText, outputText, platformText } from '@/utils/format'
import type { Listing } from '@/types'
import PageHeading from '@/components/ui/PageHeading.vue'
import PageState from '@/components/ui/PageState.vue'
import PaginationBar from '@/components/ui/PaginationBar.vue'
import AppDialog from '@/components/ui/AppDialog.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
const list = useCollection<Listing>('/listings', 10, { platform: '' }),
  selected = ref<Listing | null>(null),
  open = ref(false)
const platforms = [
  {
    name: 'Amazon',
    mark: 'a',
    description: '准备英文商品文案、主图与商品展示视频。',
  },
  {
    name: 'Shopify',
    mark: 's',
    description: '未来可将品牌内容用于独立站商品页面。',
  },
  {
    name: 'TikTok',
    mark: 't',
    description: '未来可将视频素材用于内容电商场景。',
  },
]
function viewRecord(record: Listing) {
  selected.value = record
  open.value = true
}
</script>
<template>
  <PageHeading
    title="刊登准备"
    description="在内容与渠道之间，做好最后一步准备。"
    eyebrow="PUBLISHING PREPARATION"
  >
    <button class="btn btn-primary" disabled>
      <AppIcon name="globe" :size="17" />
      发布到平台 · 尚未开放
    </button>
  </PageHeading>
  <div class="three-grid mb-5">
    <article v-for="platform in platforms" :key="platform.name" class="card platform-card">
      <div class="row between">
        <span class="provider-mark">{{ platform.mark }}</span>
        <span class="badge badge-neutral">接入筹备中</span>
      </div>
      <h3>{{ platform.name }}</h3>
      <p>{{ platform.description }}</p>
    </article>
  </div>
  <div class="notice notice-warning mb-5">
    <AppIcon name="info" :size="18" />
    <span>
      当前没有接通平台发布接口，下方仅保留已有本地记录。记录中的外部标识不代表已上架，请在平台后台核实。
    </span>
  </div>
  <div class="toolbar">
    <div class="filter-group">
      <label for="listing-platform">目标平台</label>
      <select
        id="listing-platform"
        v-model="list.params.platform"
        class="form-select"
        @change="list.reload(true)"
      >
        <option value="">全部平台</option>
        <option value="amazon">Amazon</option>
        <option value="shopify">Shopify</option>
        <option value="tiktok">TikTok</option>
      </select>
    </div>
    <button class="btn btn-secondary" :disabled="list.loading" @click="list.reload()">
      <AppIcon name="refresh" :size="16" />
      刷新记录
    </button>
  </div>
  <PageState
    :loading="list.loading"
    :error="list.error"
    :error-code="list.errorCode"
    :empty="!list.items.length"
    title="暂无本地刊登记录"
    description="真实平台发布能力尚未开放，可先在交付中心核对内容。"
    icon="globe"
    @retry="list.reload()"
  >
    <div class="panel table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>商品</th>
            <th>目标平台</th>
            <th>记录状态</th>
            <th>登记时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in list.items" :key="item.id">
            <td>
              <strong>{{ item.sku_name || '未命名商品' }}</strong>
              <small>{{ item.sku_code }}</small>
            </td>
            <td>{{ platformText(item.platform) }}</td>
            <td><span class="badge badge-neutral">已登记（本地记录）</span></td>
            <td>{{ dateText(item.create_time) }}</td>
            <td>
              <button class="text-button" @click="viewRecord(item)">
                查看记录
                <AppIcon name="arrow-right" :size="14" />
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </PageState>
  <PaginationBar
    :page="list.page"
    @change="list.page = $event"
    :total="list.total"
    :size="list.size"
    :loading="list.loading"
    :has-more="list.hasMore"
  />
  <AppDialog v-model="open" title="本地刊登记录" drawer>
    <template v-if="selected">
      <p class="notice notice-warning">此记录未验证平台上架状态。</p>
      <dl class="details-list mt-5">
        <div>
          <dt>商品</dt>
          <dd>{{ selected.sku_name || '—' }}</dd>
        </div>
        <div>
          <dt>目标平台</dt>
          <dd>{{ platformText(selected.platform) }}</dd>
        </div>
        <div>
          <dt>记录时间</dt>
          <dd>{{ dateText(selected.create_time) }}</dd>
        </div>
        <div>
          <dt>记录 ID</dt>
          <dd>{{ selected.id }}</dd>
        </div>
      </dl>
      <details class="details-toggle">
        <summary>查看原始登记内容</summary>
        <pre class="detail-json">{{ outputText(selected.listing_data) }}</pre>
      </details>
    </template>
  </AppDialog>
</template>
