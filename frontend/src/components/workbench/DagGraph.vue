<template>
  <div class="dag-graph">
    <h3>7-Agent 状态图流程可视化</h3>
    <div class="nodes-container">
      <div class="node-pill">Orchestrator</div>
      <div class="arrow">↓</div>
      <div class="node-pill">RequirementAnalyzer</div>
      <div class="arrow">↓</div>
      <div class="node-pill">CreativePlanner</div>
      <div class="arrow">↓</div>
      <div class="node-pill">VisualDesigner</div>
      <div class="arrow">↓</div>
      <div class="split-nodes">
        <div class="node-pill">ImageGenerator</div>
        <div class="node-pill">VideoGenerator</div>
      </div>
      <div class="arrow">↓</div>
      <div class="node-pill">QualityReviewer</div>
    </div>
  </div>
</template>

<script setup lang="ts">
</script>

<style scoped>
.dag-graph {
  padding: 16px;
  background: #ffffff;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}
.nodes-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
}
.node-pill {
  padding: 8px 16px;
  border-radius: 20px;
  background: #e2e8f0;
  font-weight: 500;
}
.split-nodes {
  display: flex;
  gap: 16px;
}
.arrow {
  color: #94a3b8;
}
</style>
