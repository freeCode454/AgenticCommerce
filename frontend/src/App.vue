<template>
  <div v-if="isLoginPage" class="login-layout">
    <router-view />
  </div>
  <div v-else class="app-layout">
    <!-- 左侧极客质感暗色导航侧边栏 -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <div class="logo-box">
          <span class="logo-icon">⚡</span>
          <div class="logo-text">
            <h2>AgenticCommerce</h2>
            <span class="logo-sub">自主智能体出海电商</span>
          </div>
        </div>
      </div>

      <nav class="sidebar-nav">
        <div class="nav-section-title">核心业务中台</div>
        <router-link to="/dashboard" class="nav-item" active-class="active">
          <span class="nav-icon">📊</span>
          <span class="nav-label">总览大盘</span>
        </router-link>
        <router-link to="/tasks" class="nav-item" active-class="active">
          <span class="nav-icon">🎯</span>
          <span class="nav-label">生成任务</span>
        </router-link>
        <router-link to="/batches" class="nav-item" active-class="active">
          <span class="nav-icon">📦</span>
          <span class="nav-label">批次下发</span>
        </router-link>
        <router-link to="/skus" class="nav-item" active-class="active">
          <span class="nav-icon">🏷️</span>
          <span class="nav-label">商品 SKU</span>
        </router-link>

        <div class="nav-section-title">多模态生成成果</div>
        <router-link to="/copies" class="nav-item" active-class="active">
          <span class="nav-icon">✍️</span>
          <span class="nav-label">出海文案库</span>
        </router-link>
        <router-link to="/assets" class="nav-item" active-class="active">
          <span class="nav-icon">🎨</span>
          <span class="nav-label">媒体素材资产</span>
        </router-link>
        <router-link to="/compliance" class="nav-item" active-class="active">
          <span class="nav-icon">🛡️</span>
          <span class="nav-label">合规质检报告</span>
        </router-link>
        <router-link to="/packages" class="nav-item" active-class="active">
          <span class="nav-icon">🎁</span>
          <span class="nav-label">交付物打包</span>
        </router-link>
        <router-link to="/listings" class="nav-item" active-class="active">
          <span class="nav-icon">🌐</span>
          <span class="nav-label">跨境刊登发布</span>
        </router-link>

        <div class="nav-section-title">AI 底座与系统运维</div>
        <router-link to="/knowledge" class="nav-item" active-class="active">
          <span class="nav-icon">📚</span>
          <span class="nav-label">品牌知识库 RAG</span>
        </router-link>
        <router-link to="/providers" class="nav-item" active-class="active">
          <span class="nav-icon">🔌</span>
          <span class="nav-label">AI 模型厂商配置</span>
        </router-link>
        <router-link to="/audit" class="nav-item" active-class="active">
          <span class="nav-icon">📜</span>
          <span class="nav-label">成本与审计</span>
        </router-link>
        <router-link to="/settings" class="nav-item" active-class="active">
          <span class="nav-icon">⚙️</span>
          <span class="nav-label">系统设置</span>
        </router-link>
      </nav>

      <div class="sidebar-footer">
        <div class="user-pill">
          <div class="user-avatar">JD</div>
          <div class="user-meta">
            <span class="user-name">系统管理员</span>
            <span class="user-role">Enterprise Admin</span>
          </div>
        </div>
      </div>
    </aside>

    <!-- 右侧主体内容容器 -->
    <div class="main-wrapper">
      <header class="top-header">
        <div class="header-left">
          <span class="tenant-badge">🏢 环球出海科技有限公司</span>
          <span class="env-tag">Dev (Port: 8002)</span>
        </div>
        <div class="header-right">
          <router-link to="/tasks" class="btn btn-primary btn-sm">+ 快速发起生成</router-link>
          <router-link to="/login" class="btn btn-secondary btn-sm">退出</router-link>
        </div>
      </header>

      <main class="page-content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const isLoginPage = computed(() => route.path === '/login')
</script>

<style scoped>
.app-layout {
  display: flex;
  min-height: 100vh;
}

.login-layout {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
}

.sidebar {
  width: 250px;
  background-color: var(--sidebar-bg);
  display: flex;
  flex-direction: column;
  position: fixed;
  top: 0;
  bottom: 0;
  left: 0;
  z-index: 100;
  border-right: 1px solid rgba(255, 255, 255, 0.08);
}

.sidebar-header {
  padding: 20px 18px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.logo-box {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo-icon {
  font-size: 24px;
  background: rgba(99, 102, 241, 0.2);
  border-radius: 8px;
  padding: 4px;
}

.logo-text h2 {
  font-size: 16px;
  font-weight: 700;
  color: #fff;
  letter-spacing: -0.3px;
}

.logo-sub {
  font-size: 11px;
  color: var(--text-light);
}

.sidebar-nav {
  flex: 1;
  padding: 12px;
  overflow-y: auto;
}

.nav-section-title {
  font-size: 11px;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 12px 10px 6px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border-radius: var(--radius-sm);
  color: #94a3b8;
  text-decoration: none;
  font-size: 13.5px;
  font-weight: 500;
  transition: all 0.15s ease;
  margin-bottom: 2px;
}

.nav-item:hover {
  background: var(--sidebar-hover);
  color: #fff;
}

.nav-item.active {
  background: linear-gradient(90deg, #4f46e5 0%, #6366f1 100%);
  color: #fff;
  box-shadow: 0 2px 6px rgba(79, 70, 229, 0.35);
}

.sidebar-footer {
  padding: 14px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.user-pill {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 8px;
}

.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, #6366f1, #06b6d4);
  color: #fff;
  font-weight: 700;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.user-meta {
  display: flex;
  flex-direction: column;
}

.user-name {
  color: #fff;
  font-size: 13px;
  font-weight: 500;
}

.user-role {
  color: #64748b;
  font-size: 11px;
}

.main-wrapper {
  margin-left: 250px;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.top-header {
  height: 60px;
  background: #fff;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  position: sticky;
  top: 0;
  z-index: 90;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.tenant-badge {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
  background: #f1f5f9;
  padding: 4px 10px;
  border-radius: 20px;
}

.env-tag {
  font-size: 12px;
  color: #10b981;
  background: #ecfdf5;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 600;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.page-content {
  flex: 1;
  padding: 24px;
  background: var(--bg-main);
}
</style>
