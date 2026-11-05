<script setup lang="ts">
import { ref, watch, onUnmounted } from 'vue'
import { useCollection } from '@/composables/useCollection'
import type { Sku } from '@/types'
import AppIcon from './AppIcon.vue'
import PageState from './PageState.vue'
import PaginationBar from './PaginationBar.vue'
const props = withDefaults(defineProps<{ modelValue: Sku[]; multiple?: boolean }>(), {
  multiple: false,
})
const emit = defineEmits<{ 'update:modelValue': [value: Sku[]] }>()
const list = useCollection<Sku>('/skus', 8),
  query = ref('')
let timer: ReturnType<typeof setTimeout> | undefined
watch(query, () => {
  clearTimeout(timer)
  timer = setTimeout(() => {
    list.params.q = query.value.trim() || undefined
    void list.reload(true)
  }, 300)
})
onUnmounted(() => clearTimeout(timer))
function choose(sku: Sku) {
  const present = props.modelValue.some((item) => item.id === sku.id)
  if (props.multiple) {
    if (!present && props.modelValue.length >= 100) return
    emit(
      'update:modelValue',
      present ? props.modelValue.filter((item) => item.id !== sku.id) : [...props.modelValue, sku],
    )
  } else emit('update:modelValue', [sku])
}
</script>
<template>
  <div class="search-input">
    <AppIcon name="search" :size="18" />
    <input
      v-model="query"
      type="search"
      aria-label="搜索可选商品"
      placeholder="搜索商品名称或编码"
    />
  </div>
  <p v-if="modelValue.length" class="field-help spaced">
    已选择 {{ modelValue.length }} 件：{{ modelValue.map((item) => item.name).join('、') }}
  </p>
  <PageState
    :loading="list.loading"
    :error="list.error"
    :error-code="list.errorCode"
    :empty="!list.items.length"
    title="没有找到商品"
    description="换个关键词，或先到商品资料中录入商品。"
    icon="box"
    @retry="list.reload()"
  >
    <div class="choice-list">
      <label v-for="sku in list.items" :key="sku.id" class="choice-row">
        <input
          :type="multiple ? 'checkbox' : 'radio'"
          :name="multiple ? undefined : 'chosen-sku'"
          :checked="modelValue.some((item) => item.id === sku.id)"
          :disabled="
            multiple && modelValue.length >= 100 && !modelValue.some((item) => item.id === sku.id)
          "
          @change="choose(sku)"
        />
        <span>
          <strong>{{ sku.name }}</strong>
          <small>{{ sku.code }} · {{ sku.category }}</small>
        </span>
      </label>
    </div>
    <PaginationBar
      :page="list.page"
      :size="list.size"
      :total="list.total"
      :loading="list.loading"
      @change="list.page = $event"
    />
  </PageState>
</template>
