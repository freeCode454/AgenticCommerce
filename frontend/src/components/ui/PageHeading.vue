<script setup lang="ts">
defineProps<{ title: string; description?: string; eyebrow?: string }>()
</script>
<template>
  <header class="page-heading">
    <div>
      <div class="eyebrow">
        <span class="green-dot" />
        {{ eyebrow || '你的内容创作空间' }}
      </div>
      <h1>{{ title }}</h1>
      <p v-if="description">{{ description }}</p>
    </div>
    <div class="heading-actions"><slot /></div>
  </header>
</template>
