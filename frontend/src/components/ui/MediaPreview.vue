<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import AppIcon from './AppIcon.vue'
import { safeUrl } from '@/utils/format'
import { archivePath, fetchArchive } from '@/utils/archive'
const props = withDefaults(
  defineProps<{
    src?: string
    alt?: string
    type?: string
    controls?: boolean
  }>(),
  { type: 'image', controls: false, alt: '商品图片' },
)
const failed = ref(false)
const loading = ref(false)
const preview = ref<HTMLElement>()
const visible = ref(false)
const version = ref(0)
const storedUrl = ref('')
const archived = computed(() => Boolean(archivePath(props.src)))
const url = computed(() => (archived.value ? storedUrl.value : safeUrl(props.src)))
let observer: IntersectionObserver | undefined

onMounted(() => {
  if (!preview.value || !('IntersectionObserver' in window)) {
    visible.value = true
    return
  }
  observer = new IntersectionObserver(([entry]) => {
    if (!entry?.isIntersecting) return
    visible.value = true
    observer?.disconnect()
  })
  observer.observe(preview.value)
})
onBeforeUnmount(() => observer?.disconnect())

watch(
  () => props.src,
  () => {
    version.value = 0
    failed.value = false
  },
)
watch(
  [() => props.src, () => props.type, visible, version],
  async ([src, kind, inView, attempt], _, onCleanup) => {
    storedUrl.value = ''
    loading.value = false
    if (!src || !archivePath(src) || (kind === 'video' ? !attempt : !inView)) return
    const controller = new AbortController()
    let objectUrl = ''
    onCleanup(() => {
      controller.abort()
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    })
    loading.value = true
    failed.value = false
    try {
      const { data } = await fetchArchive(src, 'asset', controller.signal)
      if (controller.signal.aborted) return
      objectUrl = URL.createObjectURL(data)
      storedUrl.value = objectUrl
    } catch {
      if (!controller.signal.aborted) failed.value = true
    } finally {
      if (!controller.signal.aborted) loading.value = false
    }
  },
)

function retry() {
  failed.value = false
  version.value++
}
</script>
<template>
  <div ref="preview" class="media-preview">
    <template v-if="url && !failed">
      <video
        v-if="type === 'video'"
        :src="url"
        :controls="controls"
        preload="metadata"
        @error="failed = true"
        :aria-label="alt"
      />
      <img v-else :src="url" :alt="alt" loading="lazy" @error="failed = true" />
    </template>
    <div v-else class="media-placeholder">
      <AppIcon :name="type === 'video' ? 'video' : 'image'" :size="34" />
      <span v-if="loading" role="status">正在加载媒体…</span>
      <template v-else-if="failed">
        <span>媒体暂时无法加载</span>
        <button type="button" class="text-button" @click="retry">重试加载</button>
      </template>
      <template v-else-if="archived && type === 'video'">
        <button v-if="controls" type="button" class="text-button" @click="retry">加载视频</button>
        <span v-else>打开详情可播放视频</span>
      </template>
      <span v-else>{{ archived ? '等待加载图片' : '暂无参考图片' }}</span>
    </div>
  </div>
</template>
