<script setup lang="ts">
withDefaults(defineProps<{ light?: boolean; iconOnly?: boolean }>(), {
  light: false,
  iconOnly: false,
})
</script>
<template>
  <span class="brand" :class="{ 'brand-light': light }">
    <img src="/brand/logo-mark.svg" width="40" height="40" alt="AgenticCommerce 标志" />
    <span v-if="!iconOnly">
      <strong>
        Agentic
        <span>Commerce</span>
      </strong>
      <small>让商品，走向更大的市场</small>
    </span>
  </span>
</template>
