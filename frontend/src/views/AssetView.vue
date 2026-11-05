<script setup lang="ts">
import { ref } from 'vue'
import { useCollection } from '@/composables/useCollection'
import { dateText, safeUrl } from '@/utils/format'
import type { Asset } from '@/types'
import PageHeading from '@/components/ui/PageHeading.vue'
import PageState from '@/components/ui/PageState.vue'
import PaginationBar from '@/components/ui/PaginationBar.vue'
import MediaPreview from '@/components/ui/MediaPreview.vue'
import AppDialog from '@/components/ui/AppDialog.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
const list = useCollection<Asset>('/assets', 12, { type: '', sub_type: '' }),
  selected = ref<Asset | null>(null),
  open = ref(false)
function view(asset: Asset) {
  selected.value = asset
  open.value = true
}
function kind(asset: Asset) {
  return (
    (
      {
        main: '商品主图',
        scene: '场景图',
        detail: '细节图',
        product_showcase: '展示视频',
      } as Record<string, string>
    )[asset.sub_type || ''] || (asset.type === 'video' ? '视频' : '图片')
  )
}
</script>
<template>
  <PageHeading
    title="素材库"
    description="每一次创作，都在这里积累为品牌资产。"
    eyebrow="CONTENT LIBRARY"
  />
  <div class="toolbar">
    <div class="filter-group">
      <label for="asset-type">素材类型</label>
      <select
        id="asset-type"
        v-model="list.params.type"
        class="form-select"
        @change="list.reload(true)"
      >
        <option value="">全部类型</option>
        <option value="image">图片</option>
        <option value="video">视频</option>
      </select>
    </div>
    <div class="filter-group">
      <label for="asset-view">素材视角</label>
      <select
        id="asset-view"
        v-model="list.params.sub_type"
        class="form-select"
        @change="list.reload(true)"
      >
        <option value="">全部视角</option>
        <option value="main">商品主图</option>
        <option value="scene">场景图</option>
        <option value="detail">细节图</option>
        <option value="product_showcase">展示视频</option>
      </select>
    </div>
    <button class="btn btn-secondary" :disabled="list.loading" @click="list.reload()">
      <AppIcon name="refresh" :size="16" />
      刷新
    </button>
  </div>
  <PageState
    :loading="list.loading"
    :error="list.error"
    :error-code="list.errorCode"
    :empty="!list.items.length"
    title="暂无匹配素材"
    description="调整筛选条件，或在商品资料中创建一次生成任务。"
    icon="image"
    @retry="list.reload()"
  >
    <div class="media-grid">
      <article v-for="asset in list.items" :key="asset.id" class="media-card">
        <div class="media-open">
          <MediaPreview :src="asset.url" :type="asset.type" :alt="asset.sku_name || kind(asset)" />
        </div>
        <div class="media-card-body">
          <div class="row between">
            <span class="badge badge-neutral">{{ kind(asset) }}</span>
            <span v-if="asset.is_mock" class="badge badge-warning">示例素材</span>
          </div>
          <h3 class="mt-3">{{ asset.sku_name || '未关联商品名称' }}</h3>
          <p>
            {{ asset.sku_code || asset.sku_id }} ·
            {{ dateText(asset.create_time) }}
          </p>
          <button class="text-button mt-3" @click="view(asset)">
            查看素材
            <AppIcon name="arrow-right" :size="14" />
          </button>
        </div>
      </article>
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
  <AppDialog v-model="open" title="素材预览" wide>
    <template v-if="selected">
      <div class="media-full">
        <MediaPreview
          :src="selected.url"
          :type="selected.type"
          :alt="selected.sku_name || '素材预览'"
          controls
        />
      </div>
      <dl class="details-list">
        <div>
          <dt>关联商品</dt>
          <dd>{{ selected.sku_name || '—' }}</dd>
        </div>
        <div>
          <dt>素材类型</dt>
          <dd>{{ kind(selected) }}</dd>
        </div>
        <div>
          <dt>生成时间</dt>
          <dd>{{ dateText(selected.create_time) }}</dd>
        </div>
        <div>
          <dt>素材 ID</dt>
          <dd>{{ selected.id }}</dd>
        </div>
      </dl>
      <p v-if="selected.is_mock" class="notice notice-warning mt-4">
        这是一条后端标记的示例素材，请核实后再用于交付。
      </p>
    </template>
    <template #footer>
      <RouterLink
        v-if="selected?.task_id"
        class="btn btn-secondary"
        :to="`/workbench/${selected.task_id}`"
        @click="open = false"
      >
        查看任务
      </RouterLink>
      <a
        v-if="safeUrl(selected?.url)"
        class="btn btn-primary"
        :href="safeUrl(selected?.url)"
        target="_blank"
        rel="noopener noreferrer"
      >
        打开原文件
        <AppIcon name="external" :size="15" />
      </a>
    </template>
  </AppDialog>
</template>
