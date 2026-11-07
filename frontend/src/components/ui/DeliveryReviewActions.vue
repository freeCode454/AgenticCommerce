<script setup lang="ts">
import { computed, ref } from 'vue'
import client from '@/api/client'
import { useUiStore } from '@/stores/ui'
import { useUserStore } from '@/stores/user'
import { errorMessage } from '@/utils/format'
import { createSubmissionKey } from '@/utils/submissionKey'
import type { ApiResponse, Report, TaskDetail } from '@/types'
import AppDialog from './AppDialog.vue'

const props = defineProps<{ detail: TaskDetail }>()
const emit = defineEmits<{ changed: [] }>()
const ui = useUiStore()
const user = useUserStore()
const report = computed(() => props.detail.compliance_report)
const base = computed(() => `/compliance/tasks/${encodeURIComponent(props.detail.task.id)}`)
const reviewKey = createSubmissionKey()
const checking = ref(false)
const checkFailure = ref('')
const open = ref(false)
const saving = ref(false)
const decision = ref<'approved' | 'rejected'>('approved')
const targetReport = ref('')
const confirmed = ref(false)
const note = ref('')
const decisionFailure = ref('')
const canDecide = computed(() =>
  props.detail.task.status === 'completed' && report.value?.passed === 1 && !!report.value.id
  && report.value.human_review?.decision === 'pending',
)

async function checkCopy() {
  if (checking.value || report.value?.status === 'reviewing') return
  const payload = { report_id: report.value?.id || null }
  if (!(await ui.confirm(
    '仅重新审核文案',
    '使用当前语言模型核对文案和商品资料，可能产生费用。已有图片和视频会继续沿用。',
    '开始重审',
  ))) return
  checking.value = true
  checkFailure.value = ''
  try {
    const { data } = await client.post<ApiResponse<Report>>(`${base.value}/copy-review`, payload, {
      headers: { 'Idempotency-Key': reviewKey.forPayload([base.value, payload]) },
      timeout: 90_000,
    })
    if (data.data.status !== 'reviewing') reviewKey.reset()
    emit('changed')
  } catch (error) {
    checkFailure.value = errorMessage(error)
  } finally {
    checking.value = false
  }
}

function startDecision(value: 'approved' | 'rejected') {
  if (!report.value?.id) return
  targetReport.value = report.value.id
  decision.value = value
  confirmed.value = false
  note.value = ''
  decisionFailure.value = ''
  open.value = true
}

async function saveDecision() {
  if (saving.value || (decision.value === 'approved' ? !confirmed.value : !note.value.trim())) return
  saving.value = true
  decisionFailure.value = ''
  try {
    await client.post(`${base.value}/human-review`, {
      report_id: targetReport.value,
      decision: decision.value,
      note: note.value.trim(),
    })
    open.value = false
    ui.notify('人工审核结论已保存')
    emit('changed')
  } catch (error) {
    decisionFailure.value = errorMessage(error)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <section v-if="detail.task.status === 'review_required'" class="notice notice-warning wrap mt-5">
    <div>
      <p v-if="!detail.review_media_complete">当前任务缺少可复用的同轮真实素材。</p>
      <p v-else-if="checking || report?.status === 'reviewing'">文案重审进行中，可以刷新查看结果。</p>
      <p v-else>重审当前文案，沿用本轮生成的图片和视频。</p>
      <p v-if="checkFailure" role="alert">{{ checkFailure }}</p>
    </div>
    <button v-if="checking || report?.status === 'reviewing'" class="btn btn-secondary" @click="emit('changed')">
      刷新审核状态
    </button>
    <button v-else class="btn btn-primary" :disabled="!detail.review_media_complete" @click="checkCopy">
      仅重审文案
    </button>
  </section>
  <section v-if="canDecide" class="notice wrap mt-5">
    <div>
      <p>交付前请核对本任务的文案、三张图片和视频。</p>
      <p v-if="user.userInfo?.role !== 'admin'">等待工作空间管理员提交审核结论。</p>
      <p v-else-if="!detail.review_media_complete">当前素材不完整，暂不能批准交付。</p>
    </div>
    <div v-if="user.userInfo?.role === 'admin'" class="row wrap">
      <button class="btn btn-secondary" @click="startDecision('rejected')">驳回交付</button>
      <button class="btn btn-primary" :disabled="!detail.review_media_complete" @click="startDecision('approved')">
        批准交付
      </button>
    </div>
  </section>
  <AppDialog v-model="open" :title="decision === 'approved' ? '确认批准交付' : '驳回交付'" :busy="saving">
    <form id="delivery-decision" class="form-stack" @submit.prevent="saveDecision">
      <p v-if="decisionFailure" class="notice notice-danger" role="alert">{{ decisionFailure }}</p>
      <label v-if="decision === 'approved'" class="row">
        <input v-model="confirmed" type="checkbox" :disabled="saving" required />
        我已核对当前文案、三张图片和视频，同意交付。
      </label>
      <div class="form-group">
        <label for="delivery-note">{{ decision === 'rejected' ? '驳回原因' : '审核备注（选填）' }}</label>
        <textarea id="delivery-note" v-model="note" class="form-textarea" maxlength="1000"
          :required="decision === 'rejected'" :disabled="saving" rows="4" />
      </div>
    </form>
    <template #footer>
      <button class="btn btn-secondary" :disabled="saving" @click="open = false">取消</button>
      <button class="btn btn-primary" type="submit" form="delivery-decision"
        :disabled="saving || (decision === 'approved' ? !confirmed : !note.trim())">
        {{ saving ? '正在保存…' : '保存审核结论' }}
      </button>
    </template>
  </AppDialog>
</template>
