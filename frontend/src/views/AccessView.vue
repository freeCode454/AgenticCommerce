<script setup lang="ts">
import { useRoute } from 'vue-router'
import AppIcon from '@/components/ui/AppIcon.vue'
const route = useRoute()
</script>
<template>
  <section class="empty-state access-state">
    <span class="empty-icon">
      <AppIcon :name="route.meta.forbidden ? 'lock' : 'search'" :size="32" />
    </span>
    <h1>{{ route.meta.forbidden ? '暂无访问权限' : '这个页面还没到站' }}</h1>
    <p>
      {{
        route.meta.forbidden
          ? '此功能仅限管理员使用，请联系你的企业管理员。'
          : '页面可能已移动，请从导航中重新选择。'
      }}
    </p>
    <RouterLink class="btn btn-primary" to="/dashboard">
      返回工作台
      <AppIcon name="arrow-right" :size="16" />
    </RouterLink>
  </section>
</template>
