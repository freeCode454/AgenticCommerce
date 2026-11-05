<script setup lang="ts">
import AppIcon from './AppIcon.vue'
</script>
<template>
  <div class="creative-canvas" aria-hidden="true">
    <div class="canvas-grid" />
    <div class="floating-tag">
      <span class="green-dot" />
      让灵感，成为品牌内容
    </div>
    <div class="campaign-card">
      <div class="campaign-top">
        THE EVERYDAY COLLECTION
        <AppIcon name="spark" :size="13" />
      </div>
      <img class="headphone-art" src="/brand/creative-headphones.svg" alt="" />
      <div class="campaign-type">
        Everyday,
        <br />
        <em>elevated.</em>
      </div>
      <div class="campaign-footer">
        DESIGNED TO GO FURTHER
        <span>↗</span>
      </div>
    </div>
    <div class="mini-copy-card">
      <span>
        <AppIcon name="file" :size="14" />
        创意示意
      </span>
      <strong>
        Sound good.
        <br />
        Feel even better.
      </strong>
      <div class="copy-lines">
        <i />
        <i />
        <i />
      </div>
      <small>
        <AppIcon name="check" :size="12" />
        为你的品牌而写
      </small>
    </div>
    <span class="canvas-star">✳</span>
  </div>
</template>
