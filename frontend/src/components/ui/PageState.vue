<script setup lang="ts">
import AppIcon from './AppIcon.vue'
withDefaults(
  defineProps<{
    loading?: boolean
    error?: string
    empty?: boolean
    title?: string
    description?: string
    icon?: string
    errorCode?: number
  }>(),
  {
    loading: false,
    error: '',
    empty: false,
    title: '这里还没有内容',
    description: '完成第一次创作后，你的内容会出现在这里。',
    icon: 'layers',
    errorCode: 0,
  },
)
defineEmits<{ retry: [] }>()
</script>
<template>
  <div v-if="loading" class="loading-state" role="status" aria-label="正在加载" aria-busy="true">
    <span class="spinner" />
    <span>正在加载内容…</span>
    <div class="skeleton-lines">
      <i />
      <i />
      <i />
    </div>
  </div>
  <div v-else-if="error" class="empty-state error-state" role="alert">
    <span class="empty-icon">
      <AppIcon :name="errorCode === 403 ? 'lock' : 'warning'" :size="28" />
    </span>
    <h2>{{ errorCode === 403 ? '暂无访问权限' : '暂时无法加载' }}</h2>
    <p>{{ error }}</p>
    <button v-if="errorCode !== 403" class="btn btn-secondary" @click="$emit('retry')">
      <AppIcon name="refresh" :size="16" />
      重新加载
    </button>
  </div>
  <div v-else-if="empty" class="empty-state">
    <span class="empty-icon"><AppIcon :name="icon" :size="28" /></span>
    <h2>{{ title }}</h2>
    <p>{{ description }}</p>
    <slot name="action" />
  </div>
  <slot v-else />
</template>
