<script setup lang="ts">
import { useResource } from '@/composables/useResource'
import { useUserStore } from '@/stores/user'
import type { SystemStatus } from '@/types'
import PageHeading from '@/components/ui/PageHeading.vue'
import PageState from '@/components/ui/PageState.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import BrandLogo from '@/components/ui/BrandLogo.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
const user = useUserStore(),
  { data, loading, error, errorCode, reload } = useResource<SystemStatus>('/system/status')
const services = [
  {
    key: 'postgres',
    name: '业务数据库',
    icon: 'database',
    description: '保存商品、任务与内容记录。',
  },
  {
    key: 'redis',
    name: '任务与缓存',
    icon: 'layers',
    description: '支持任务执行与实时状态通信。',
  },
  {
    key: 'storage',
    name: '媒体存储',
    icon: 'image',
    description: '保存生成的图片与视频文件。',
  },
]
</script>
<template>
  <PageHeading
    title="工作空间设置"
    description="查看当前身份、服务状态与品牌资源。"
    eyebrow="WORKSPACE SETTINGS"
  >
    <button class="btn btn-secondary" :disabled="loading" @click="reload()">
      <AppIcon name="refresh" :size="16" />
      检查服务状态
    </button>
  </PageHeading>
  <div class="two-grid mb-5">
    <section class="card">
      <h2 class="content-title mb-4">当前工作空间</h2>
      <dl class="details-list">
        <div>
          <dt>工作空间名称</dt>
          <dd>
            {{ data?.tenant_name || user.userInfo?.tenant_name || '暂不可用' }}
          </dd>
        </div>
        <div>
          <dt>工作空间 ID</dt>
          <dd>
            {{ data?.tenant_id || user.userInfo?.tenant_id || '暂不可用' }}
          </dd>
        </div>
      </dl>
      <p class="field-hint mt-4">所有内容与用量均以当前工作空间为范围。</p>
    </section>
    <section class="card">
      <h2 class="content-title mb-4">我的账号</h2>
      <dl class="details-list">
        <div>
          <dt>姓名</dt>
          <dd>{{ user.userInfo?.name || '暂不可用' }}</dd>
        </div>
        <div>
          <dt>邮箱</dt>
          <dd>{{ user.userInfo?.email || '暂不可用' }}</dd>
        </div>
        <div>
          <dt>角色</dt>
          <dd>
            {{ user.userInfo?.role === 'admin' ? '管理员' : user.userInfo?.role || '暂不可用' }}
          </dd>
        </div>
      </dl>
    </section>
  </div>
  <div class="section-heading">
    <div>
      <h2>服务状态</h2>
      <p>显示服务端最近一次实际检查结果。</p>
    </div>
  </div>
  <PageState :loading="loading" :error="error" :error-code="errorCode" @retry="reload()">
    <div class="service-grid mb-5">
      <article v-for="service in services" :key="service.key" class="service-card">
        <AppIcon :name="service.icon" :size="24" />
        <h3>{{ service.name }}</h3>
        <StatusBadge
          :status="data?.dependencies[service.key] || 'unknown'"
          :label="data?.dependencies[service.key] ? '' : '未提供状态'"
        />
        <p>{{ service.description }}</p>
      </article>
    </div>
  </PageState>
  <section class="card mt-5">
    <div class="settings-brand">
      <div>
        <h2 class="content-title">品牌资源</h2>
        <BrandLogo />
        <p class="text-muted text-sm">统一用于登录页、导航与项目资料。</p>
      </div>
      <div class="asset-links">
        <a
          class="btn btn-secondary btn-sm"
          href="/brand/logo-mark.svg"
          download="AgenticCommerce-mark.svg"
        >
          SVG 图形
        </a>
        <a
          class="btn btn-secondary btn-sm"
          href="/brand/logo-wordmark.svg"
          download="AgenticCommerce-wordmark.svg"
        >
          SVG 字标
        </a>
        <a
          class="btn btn-secondary btn-sm"
          href="/brand/logo-512.png"
          download="AgenticCommerce-512.png"
        >
          PNG 512px
        </a>
        <a
          class="btn btn-secondary btn-sm"
          href="/brand/logo-1024.png"
          download="AgenticCommerce-1024.png"
        >
          PNG 1024px
        </a>
      </div>
    </div>
  </section>
</template>
