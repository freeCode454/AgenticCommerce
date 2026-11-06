<script setup lang="ts">
import { ref, watch } from 'vue'
import { createSubmissionKey } from '@/utils/submissionKey'
import client from '@/api/client'
import { useUiStore } from '@/stores/ui'
import { errorMessage } from '@/utils/format'
import type { Sku, ApiResponse } from '@/types'
import AppDialog from './AppDialog.vue'
import AppIcon from './AppIcon.vue'
import SkuPicker from './SkuPicker.vue'
const props = defineProps<{ modelValue: boolean; sku?: Sku }>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  created: [id: string]
}>()
const selected = ref<Sku[]>(props.sku ? [props.sku] : []),
  retries = ref(2),
  busy = ref(false),
  error = ref('')
const ui = useUiStore()
const submissionKey = createSubmissionKey()
watch(
  () => props.modelValue,
  (open) => {
    if (open) submissionKey.reset()
  },
)
async function submit() {
  if (busy.value) return
  if (!selected.value.length) {
    error.value = '请先选择一个商品'
    return
  }
  busy.value = true
  error.value = ''
  try {
    const payload = {
      sku_id: selected.value[0].id,
      config: {
        language: 'en',
        platform: 'amazon',
        media_type: 'both',
        max_retries: retries.value,
      },
    }
    const response = await client.post<ApiResponse<{ task_id: string }>>('/tasks', payload, {
      headers: { 'Idempotency-Key': submissionKey.forPayload(payload) },
    })
    submissionKey.reset()
    ui.notify('任务已创建，正在进入生成工作台')
    emit('update:modelValue', false)
    emit('created', response.data.data.task_id)
  } catch (cause) {
    error.value = errorMessage(cause, '任务创建失败，请重试。')
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <AppDialog
    :model-value="modelValue"
    title="开始一次新创作"
    description="选好商品，让创作有个好的起点。"
    :busy="busy"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <form id="task-create-form" @submit.prevent="submit">
      <div class="field">
        <span class="field-label">选择商品</span>
        <SkuPicker v-model="selected" />
      </div>
      <div class="form-section">
        <h3>完整内容生成</h3>
        <p>英文 Amazon 文案、商品图片及短视频，依次执行并审核。</p>
        <div class="chip-list spaced">
          <span class="tag">英文文案</span>
          <span class="tag">商品图片</span>
          <span class="tag">短视频</span>
        </div>
      </div>
      <div class="form-grid">
        <div class="field">
          <label for="task-platform">目标平台</label>
          <select id="task-platform" class="select" disabled>
            <option>Amazon · 英文</option>
          </select>
          <small class="field-help">其他平台生成适配暂未开放。</small>
        </div>
        <div class="field">
          <label for="task-retries">审核未通过时的重试上限</label>
          <select id="task-retries" v-model.number="retries" class="select" :disabled="busy">
            <option :value="0">不自动重试</option>
            <option :value="1">最多 1 次</option>
            <option :value="2">最多 2 次</option>
          </select>
        </div>
      </div>
      <p class="disabled-option">
        <AppIcon name="lock" :size="17" />
        仅图片 / 仅视频的独立执行暂未开放。
      </p>
      <p class="cost-note">
        <AppIcon name="info" :size="16" />
        开始后将调用真实模型，生成及自动重试可能产生费用。
      </p>
      <p v-if="error" class="form-error" role="alert">{{ error }}</p>
    </form>
    <template #footer>
      <button class="btn btn-secondary" :disabled="busy" @click="emit('update:modelValue', false)">
        取消
      </button>
      <button
        class="btn btn-primary"
        form="task-create-form"
        type="submit"
        :disabled="busy || !selected.length"
      >
        <span v-if="busy" class="spinner" />
        <AppIcon v-else name="spark" :size="17" />
        {{ busy ? '正在创建…' : '开始完整生成' }}
      </button>
    </template>
  </AppDialog>
</template>
