<script setup lang="ts">
import { useUiStore } from '@/stores/ui'
import AppIcon from './AppIcon.vue'
import AppDialog from './AppDialog.vue'
const ui = useUiStore()
</script>
<template>
  <Teleport to="body">
    <div class="toast-stack" aria-live="polite">
      <div
        v-for="toast in ui.toasts"
        :key="toast.id"
        class="toast"
        :class="`toast-${toast.tone}`"
        :role="toast.tone === 'error' ? 'alert' : 'status'"
      >
        <AppIcon
          :name="toast.tone === 'error' ? 'warning' : toast.tone === 'success' ? 'check' : 'info'"
        />
        <span>{{ toast.message }}</span>
        <button class="icon-button" aria-label="关闭通知" @click="ui.dismiss(toast.id)">
          <AppIcon name="close" :size="16" />
        </button>
      </div>
    </div>
  </Teleport>
  <AppDialog
    :model-value="!!ui.confirmation"
    :title="ui.confirmation?.title || '确认操作'"
    @update:model-value="ui.answer(false)"
  >
    <p class="prose">{{ ui.confirmation?.message }}</p>
    <template #footer>
      <button class="btn btn-secondary" @click="ui.answer(false)">取消</button>
      <button
        class="btn"
        :class="ui.confirmation?.danger ? 'btn-danger' : 'btn-primary'"
        @click="ui.answer(true)"
      >
        {{ ui.confirmation?.action }}
      </button>
    </template>
  </AppDialog>
</template>
