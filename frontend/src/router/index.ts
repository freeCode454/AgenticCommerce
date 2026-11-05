import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', name: 'Dashboard', component: () => import('@/views/DashboardView.vue') },
  { path: '/batches', name: 'Batches', component: () => import('@/views/BatchView.vue') },
  { path: '/tasks', name: 'Tasks', component: () => import('@/views/TaskView.vue') },
  { path: '/workbench/:taskId', name: 'Workbench', component: () => import('@/views/WorkbenchView.vue') },
  { path: '/assets', name: 'Assets', component: () => import('@/views/AssetView.vue') },
  { path: '/copies', name: 'Copies', component: () => import('@/views/CopyView.vue') },
  { path: '/knowledge', name: 'Knowledge', component: () => import('@/views/KnowledgeView.vue') },
  { path: '/providers', name: 'Providers', component: () => import('@/views/ProviderView.vue') },
  { path: '/skus', name: 'Skus', component: () => import('@/views/SkuView.vue') },
  { path: '/listings', name: 'Listings', component: () => import('@/views/ListingView.vue') },
  { path: '/audit', name: 'Audit', component: () => import('@/views/AuditView.vue') },
  { path: '/settings', name: 'Settings', component: () => import('@/views/SettingsView.vue') },
  { path: '/login', name: 'Login', component: () => import('@/views/LoginView.vue') },
  { path: '/packages', name: 'Packages', component: () => import('@/views/PackageView.vue') },
  { path: '/compliance', name: 'Compliance', component: () => import('@/views/ComplianceView.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
