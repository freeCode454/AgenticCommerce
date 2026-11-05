<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import AppIcon from './AppIcon.vue'
import { safeUrl } from '@/utils/format'
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
const url = computed(() => safeUrl(props.src))
watch(
  () => props.src,
  () => (failed.value = false),
)
</script>
<template>
  <div class="media-preview">
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
      <span>{{ failed ? '媒体暂时无法加载' : '暂无参考图片' }}</span>
      <button v-if="failed" class="text-button" @click="failed = false">重试加载</button>
    </div>
  </div>
</template>
