<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useCollection } from '@/composables/useCollection'
import type { Task } from '@/types'
import { dateText, platformText } from '@/utils/format'
import PageHeading from '@/components/ui/PageHeading.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import PageState from '@/components/ui/PageState.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import PaginationBar from '@/components/ui/PaginationBar.vue'
import TaskCreateDialog from '@/components/ui/TaskCreateDialog.vue'
const route = useRoute(),
  router = useRouter(),
  list = useCollection<Task>('/tasks', 12),
  status = ref(''),
  showCreate = ref(false)
watch(
  () => route.query.new,
  (value) => {
    if (value === '1') {
      showCreate.value = true
      void router.replace({ path: '/tasks', query: {} })
    }
  },
  { immediate: true },
)
watch(status, () => {
  list.params.status = status.value || undefined
  void list.reload(true)
})
</script>
<template>
  <PageHeading title="生成任务" description="从创建到交付，在一个地方掌握所有进展。">
    <button class="btn btn-primary" @click="showCreate = true">
      <AppIcon name="plus" :size="17" />
      新建任务
    </button>
  </PageHeading>
  <div class="section-toolbar">
    <div class="filter-bar">
      <label class="subtle" for="task-status">任务状态</label>
      <select id="task-status" v-model="status" class="select">
        <option value="">全部状态</option>
        <option value="pending">待处理</option>
        <option value="running">创作中</option>
        <option value="retrying">重新创作中</option>
        <option value="completed">已完成</option>
        <option value="failed">执行失败</option>
        <option value="review_required">待重新审核</option>
      </select>
    </div>
    <button class="btn btn-secondary btn-sm" :disabled="list.loading" @click="list.reload()">
      <AppIcon name="refresh" :size="16" />
      刷新
    </button>
  </div>
  <section class="panel">
    <PageState
      :loading="list.loading"
      :error="list.error"
      :error-code="list.errorCode"
      :empty="!list.items.length"
      title="还没有相关任务"
      description="选择一个商品，开始你的下一次创作。"
      @retry="list.reload()"
    >
      <template #action>
        <button class="btn btn-primary" @click="showCreate = true">创建生成任务</button>
      </template>
      <div class="table-scroll">
        <table class="data-table">
          <thead>
            <tr>
              <th>商品 / 任务</th>
              <th>平台与内容</th>
              <th>状态</th>
              <th>创建时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="task in list.items" :key="task.id">
              <td class="table-main">
                <strong>{{ task.sku_name || '未命名商品' }}</strong>
                <small>{{ task.sku_code || task.sku_id }}</small>
                <small class="code-pill">{{ task.id }}</small>
              </td>
              <td>
                <span class="platform-tag">{{ platformText(task.config?.platform) }}</span>
                <p class="subtle">英文文案 · 图片 · 视频</p>
              </td>
              <td><StatusBadge :status="task.status" /></td>
              <td class="subtle">{{ dateText(task.create_time) }}</td>
              <td>
                <RouterLink :to="`/workbench/${task.id}`" class="btn btn-secondary btn-sm">
                  打开工作台
                  <AppIcon name="arrow-right" :size="15" />
                </RouterLink>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <PaginationBar
        :page="list.page"
        :size="list.size"
        :total="list.total"
        :loading="list.loading"
        @change="list.page = $event"
      />
    </PageState>
  </section>
  <TaskCreateDialog
    v-if="showCreate"
    v-model="showCreate"
    @created="router.push(`/workbench/${$event}`)"
  />
</template>
