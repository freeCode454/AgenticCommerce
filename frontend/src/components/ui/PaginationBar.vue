<script setup lang="ts">
import AppIcon from './AppIcon.vue'
defineProps<{
  page: number
  total: number
  size: number
  loading?: boolean
  hasMore?: boolean
  unknownTotal?: boolean
}>()
defineEmits<{ change: [page: number] }>()
</script>
<template>
  <footer v-if="total > 0 || page > 1" class="pagination">
    <span>
      {{
        unknownTotal
          ? `第 ${page} 页`
          : `共 ${total} 条 · 第 ${page} / ${Math.max(1, Math.ceil(total / size))} 页`
      }}
    </span>
    <div>
      <button
        class="btn btn-secondary btn-sm"
        :disabled="page <= 1 || loading"
        aria-label="上一页"
        @click="$emit('change', page - 1)"
      >
        <AppIcon name="chevron-left" :size="16" />
        上一页
      </button>
      <button
        class="btn btn-secondary btn-sm"
        :disabled="loading || (unknownTotal ? !hasMore : page * size >= total)"
        aria-label="下一页"
        @click="$emit('change', page + 1)"
      >
        下一页
        <AppIcon name="chevron-right" :size="16" />
      </button>
    </div>
  </footer>
</template>
