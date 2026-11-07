<script setup lang="ts">
import { ref } from 'vue'
import { archiveErrorMessage, archivePath, saveArchive } from '@/utils/archive'
import AppIcon from './AppIcon.vue'

const props = withDefaults(defineProps<{ url?: string | null; kind?: 'asset' | 'package' }>(), {
  kind: 'asset',
})
const emit = defineEmits<{ error: [message: string] }>()
const downloading = ref(false)

async function download() {
  if (!props.url || downloading.value) return
  downloading.value = true
  emit('error', '')
  try {
    await saveArchive(props.url, props.kind)
  } catch (error) {
    emit('error', await archiveErrorMessage(error))
  } finally {
    downloading.value = false
  }
}
</script>

<template>
  <button type="button" :disabled="downloading || !archivePath(url || undefined, kind)" @click="download">
    <AppIcon name="download" :size="16" />
    <template v-if="downloading">正在下载…</template>
    <slot v-else />
  </button>
</template>
