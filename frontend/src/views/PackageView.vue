<script setup lang="ts">
import { ref } from 'vue'
import client from '@/api/client'
import { useCollection } from '@/composables/useCollection'
import { useUiStore } from '@/stores/ui'
import { dateText, errorMessage, fullCopy, safeUrl } from '@/utils/format'
import type { ApiResponse, PackageItem, DeliveryManifest } from '@/types'
import PageHeading from '@/components/ui/PageHeading.vue'
import PageState from '@/components/ui/PageState.vue'
import PaginationBar from '@/components/ui/PaginationBar.vue'
import AppDialog from '@/components/ui/AppDialog.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import ArchiveDownload from '@/components/ui/ArchiveDownload.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { archivePath } from '@/utils/archive'
const ui = useUiStore(),
  list = useCollection<PackageItem>('/packages', 10),
  open = ref(false),
  loading = ref(false),
  failure = ref(''),
  downloadFailure = ref(''),
  manifest = ref<DeliveryManifest | null>(null),
  selected = ref('')
let sequence = 0
async function view(id: string) {
  const seq = ++sequence
  selected.value = id
  open.value = true
  loading.value = true
  manifest.value = null
  failure.value = ''
  downloadFailure.value = ''
  try {
    const { data } = await client.post<ApiResponse<DeliveryManifest>>('/packages/export', {
      task_id: id,
    })
    if (seq === sequence) manifest.value = data.data
  } catch (e) {
    if (seq === sequence) failure.value = errorMessage(e)
  } finally {
    if (seq === sequence) loading.value = false
  }
}
</script>
<template>
  <PageHeading
    title="交付中心"
    description="汇集已完成任务，核对文案、媒体与审核结果。"
    eyebrow="READY FOR DELIVERY"
  />
  <div class="notice mb-5">
    <AppIcon name="info" :size="18" />
    <span>
      通过机器审核及人工批准且归档完整的任务，可在交付清单中下载 ZIP。
    </span>
  </div>
  <PageState
    :loading="list.loading"
    :error="list.error"
    :error-code="list.errorCode"
    :empty="!list.items.length"
    title="还没有待交付内容"
    description="完成生成任务后，在这里核对最终内容。"
    icon="download"
    @retry="list.reload()"
  >
    <div class="panel table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>商品</th>
            <th>关联任务</th>
            <th>完成时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in list.items" :key="item.task_id">
            <td>
              <strong>{{ item.sku_name || '未命名商品' }}</strong>
              <small>{{ item.sku_code }}</small>
            </td>
            <td>
              <RouterLink class="text-button" :to="`/workbench/${item.task_id}`">
                {{ item.task_id }}
              </RouterLink>
            </td>
            <td>{{ dateText(item.create_time) }}</td>
            <td>
              <button class="text-button" @click="view(item.task_id)">
                查看交付清单
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
    unknown-total
  />
  <AppDialog v-model="open" title="交付清单" drawer>
    <PageState :loading="loading" :error="failure" @retry="view(selected)">
      <template v-if="manifest">
        <div class="row between wrap">
          <span class="status-badge status-success">
            机器审核通过 · {{ manifest.quality_audit.score }} 分
          </span>
          <StatusBadge
            v-if="manifest.quality_audit.human_review"
            :status="`human_${manifest.quality_audit.human_review.decision}`"
          />
          <button class="text-button" @click="ui.copy(fullCopy(manifest.copywriting))">
            <AppIcon name="copy" :size="15" />
            复制文案
          </button>
        </div>
        <h2 class="content-title mt-5">{{ manifest.copywriting.title }}</h2>
        <ul class="bullets mt-4">
          <li v-for="(bullet, i) in manifest.copywriting.bullets" :key="i">
            {{ bullet }}
          </li>
        </ul>
        <p class="prose mt-4">{{ manifest.copywriting.description }}</p>
        <div class="row wrap mt-4">
          <span
            v-for="(keyword, i) in manifest.copywriting.keywords"
            :key="i"
            class="badge badge-neutral"
          >
            {{ keyword }}
          </span>
        </div>
        <h3 class="content-title mt-5">媒体文件 · {{ manifest.media_assets.length }}</h3>
        <div v-for="(asset, i) in manifest.media_assets" :key="i" class="file-row">
          <AppIcon :name="asset.type === 'video' ? 'video' : 'image'" :size="20" />
          <span>
            {{ asset.type === 'video' ? '视频' : '图片' }} · {{ asset.sub_type || '媒体素材' }}
          </span>
          <ArchiveDownload
            v-if="archivePath(asset.url)"
            :url="asset.url"
            class="text-button"
            @error="downloadFailure = $event"
          >
            下载文件
          </ArchiveDownload>
          <a
            v-else-if="safeUrl(asset.url)"
            class="text-button"
            :href="safeUrl(asset.url)"
            target="_blank"
            rel="noopener noreferrer"
          >
            打开文件
            <AppIcon name="external" :size="14" />
          </a>
          <span v-else class="text-muted">地址不可用</span>
        </div>
        <div v-if="!manifest.download_archive_url" class="notice mt-5">
          <span>{{ manifest.download_block_reason || '当前清单没有可下载的 ZIP。' }}</span>
          <button class="text-button" @click="view(selected)">刷新清单</button>
          <RouterLink
            v-if="manifest.quality_audit.human_review?.decision && manifest.quality_audit.human_review.decision !== 'approved'"
            class="text-button"
            :to="{ path: `/workbench/${manifest.task_id}`, query: { tab: 'review' } }"
          >
            查看审核
          </RouterLink>
        </div>
      </template>
    </PageState>
    <template #footer>
      <span v-if="downloadFailure" class="notice notice-danger" role="alert">{{ downloadFailure }}</span>
      <button class="btn btn-secondary" @click="open = false">关闭</button>
      <ArchiveDownload
        :url="manifest?.download_archive_url"
        kind="package"
        class="btn btn-primary"
        @error="downloadFailure = $event"
      >
        下载 ZIP
      </ArchiveDownload>
    </template>
  </AppDialog>
</template>
