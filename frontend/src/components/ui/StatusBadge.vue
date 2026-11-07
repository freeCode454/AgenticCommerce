<script setup lang="ts">
import { computed } from 'vue'
const props = defineProps<{ status?: string; label?: string }>()
const labels: Record<string, string> = {
  running: '创作中',
  retrying: '重新创作中',
  completed: '已完成',
  success: '已完成',
  failed: '执行失败',
  pending: '待处理',
  review_required: '待重新审核',
  passed: '审核通过',
  rejected: '未通过',
  outdated: '审核已失效',
  reviewing: '文案审核中',
  review_interrupted: '审核已中断',
  review_error: '审核服务异常',
  human_pending: '待人工审核',
  human_approved: '人工已批准',
  human_rejected: '人工已驳回',
  indexed: '已索引',
  active: '正常',
  disabled: '已停用',
  ready: '可用',
  unavailable: '不可用',
  draft: '草稿',
}
const tone = computed(() =>
  ['completed', 'success', 'passed', 'human_approved', 'indexed', 'active', 'ready'].includes(props.status || '')
    ? 'success'
    : ['failed', 'rejected', 'human_rejected', 'review_error', 'unavailable', 'disabled'].includes(props.status || '')
      ? 'danger'
      : ['running', 'retrying', 'review_required', 'reviewing', 'review_interrupted', 'human_pending', 'outdated', 'pending'].includes(
            props.status || '',
          )
        ? 'warning'
        : 'neutral',
)
</script>
<template>
  <span class="status-badge" :class="`status-${tone}`">
    <i />
    {{ label || labels[status || ''] || status || '暂无状态' }}
  </span>
</template>
