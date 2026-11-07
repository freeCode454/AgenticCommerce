<script setup lang="ts">
import type { Report } from '@/types'
import { dateText, outputText } from '@/utils/format'
import StatusBadge from './StatusBadge.vue'
defineProps<{ report: Report }>()
const dimensions: Record<string, string> = {
  brand_consistency: '品牌一致性',
  platform_compliance: '平台规范',
  readability: '可读性',
  visual_quality: '视觉质量',
  legal_safety: '合规安全',
}
</script>
<template>
  <div class="report-score">
    <span class="score-circle" :class="{ 'score-rejected': !report.passed }">
      {{ report.score }}
    </span>
    <div>
      <StatusBadge :status="report.status || (report.passed ? 'passed' : 'rejected')" />
      <p class="subtle spaced">
        {{ report.scope === 'copy' ? '本次机器审核仅检查文案。' : '机器辅助审核结果，素材画面需人工复核。' }}
      </p>
    </div>
  </div>
  <div v-if="report.human_review && (report.passed || report.human_review.decision !== 'pending')" class="notice mb-5">
    <StatusBadge :status="`human_${report.human_review.decision}`" />
    <span v-if="report.human_review.reviewed_at">
      {{ dateText(report.human_review.reviewed_at) }}
      {{ report.human_review.note }}
      <small v-if="report.status === 'outdated'"> · 历史结论</small>
    </span>
  </div>
  <div v-if="report.dimensions" class="score-dimensions">
    <div v-for="(value, key) in report.dimensions" :key="key" class="dimension">
      <span>{{ dimensions[String(key)] || key }}</span>
      <strong>{{ value }}</strong>
    </div>
  </div>
  <h3>需要关注的问题</h3>
  <ul v-if="report.violations?.length" class="report-list">
    <li v-for="(item, index) in report.violations" :key="index">
      {{ outputText(item) }}
    </li>
  </ul>
  <p v-else class="prose spaced">本次报告未列出违规项。</p>
  <h3 class="spaced">审核建议</h3>
  <ul v-if="report.suggestions?.length" class="bullets">
    <li v-for="item in report.suggestions" :key="item">{{ item }}</li>
  </ul>
  <p v-else class="muted spaced">暂无附加建议。</p>
</template>
