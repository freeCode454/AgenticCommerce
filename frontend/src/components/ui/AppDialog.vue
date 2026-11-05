<script setup lang="ts">
import { ref, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import AppIcon from './AppIcon.vue'
const props = withDefaults(
  defineProps<{
    modelValue: boolean
    title: string
    description?: string
    busy?: boolean
    drawer?: boolean
    wide?: boolean
  }>(),
  { busy: false, drawer: false, wide: false },
)
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()
const dialog = ref<HTMLDialogElement>()
const titleId = `dialog-${Math.random().toString(36).slice(2)}`
let previous: HTMLElement | null = null
let alive = true
async function sync() {
  await nextTick()
  if (!alive || !dialog.value) return
  if (props.modelValue && !dialog.value.open) {
    previous = document.activeElement as HTMLElement
    dialog.value.showModal()
  } else if (!props.modelValue && dialog.value.open) {
    dialog.value.close()
    if (previous?.isConnected) previous.focus()
  }
}
function close() {
  if (!props.busy) emit('update:modelValue', false)
}
function trap(event: KeyboardEvent) {
  if (event.key !== 'Tab' || !dialog.value) return
  const items = Array.from(
    dialog.value.querySelectorAll<HTMLElement>(
      'button:not(:disabled),a[href],input:not(:disabled),select:not(:disabled),textarea:not(:disabled),[tabindex]:not([tabindex="-1"])',
    ),
  ).filter((item) => item.getClientRects().length && !item.closest('[inert]'))
  const first = items[0],
    last = items[items.length - 1]
  if (!first) {
    event.preventDefault()
    return
  }
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}
function outside(event: MouseEvent) {
  const rect = dialog.value?.getBoundingClientRect()
  if (
    rect &&
    (event.clientX < rect.left ||
      event.clientX > rect.right ||
      event.clientY < rect.top ||
      event.clientY > rect.bottom)
  )
    close()
}
watch(() => props.modelValue, sync)
onMounted(sync)
onBeforeUnmount(() => {
  alive = false
  dialog.value?.close()
  if (previous?.isConnected) previous.focus()
})
</script>
<template>
  <Teleport to="body">
    <dialog
      ref="dialog"
      class="app-dialog"
      :class="{ 'dialog-drawer': drawer, 'dialog-wide': wide }"
      :aria-labelledby="titleId"
      :aria-busy="busy"
      @cancel.prevent="close"
      @keydown="trap"
      @click="outside"
    >
      <header class="dialog-heading">
        <div>
          <h2 :id="titleId">{{ title }}</h2>
          <p v-if="description">{{ description }}</p>
        </div>
        <button
          type="button"
          class="icon-button"
          :disabled="busy"
          :aria-label="`关闭${title}`"
          @click="close"
        >
          <AppIcon name="close" />
        </button>
      </header>
      <div class="dialog-body"><slot /></div>
      <footer v-if="$slots.footer" class="dialog-footer">
        <slot name="footer" />
      </footer>
    </dialog>
  </Teleport>
</template>
