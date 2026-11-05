import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { statusCode } from '@/utils/format'
import { navigation } from '@/config/navigation'
const views: Record<string, () => Promise<unknown>> = {
  '/dashboard': () => import('@/views/DashboardView.vue'),
  '/skus': () => import('@/views/SkuView.vue'),
  '/tasks': () => import('@/views/TaskView.vue'),
  '/batches': () => import('@/views/BatchView.vue'),
  '/assets': () => import('@/views/AssetView.vue'),
  '/copies': () => import('@/views/CopyView.vue'),
  '/compliance': () => import('@/views/ComplianceView.vue'),
  '/packages': () => import('@/views/PackageView.vue'),
  '/listings': () => import('@/views/ListingView.vue'),
  '/knowledge': () => import('@/views/KnowledgeView.vue'),
  '/providers': () => import('@/views/ProviderView.vue'),
  '/audit': () => import('@/views/AuditView.vue'),
  '/settings': () => import('@/views/SettingsView.vue'),
}
const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/dashboard' },
  ...navigation.map(
    (item) =>
      ({
        path: item.path,
        component: views[item.path],
        meta: { title: item.title, group: item.group, admin: item.admin },
      }) as RouteRecordRaw,
  ),
  {
    path: '/login',
    component: () => import('@/views/LoginView.vue'),
    meta: { title: '登录' },
  },
  {
    path: '/workbench/:taskId',
    component: () => import('@/views/WorkbenchView.vue'),
    meta: { title: '生成工作台', group: '工作空间' },
  },
  {
    path: '/forbidden',
    component: () => import('@/views/AccessView.vue'),
    meta: { title: '访问受限', forbidden: true },
  },
  {
    path: '/:pathMatch(.*)*',
    component: () => import('@/views/AccessView.vue'),
    meta: { title: '页面不存在' },
  },
]
const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})
router.beforeEach(async (to) => {
  if (to.path === '/login') return true
  const user = useUserStore()
  if (!user.token) return { path: '/login', query: { redirect: to.fullPath } }
  if (!user.userInfo) {
    try {
      await user.fetchUser()
    } catch (error) {
      if (statusCode(error) === 401 || !user.token)
        return { path: '/login', query: { redirect: to.fullPath } }
    }
  }
  if (to.meta.admin && user.userInfo && user.userInfo.role !== 'admin')
    return { path: '/forbidden' }
  return true
})
router.afterEach((to) => {
  document.title = `${String(to.meta.title || '工作台')} · AgenticCommerce`
})
export default router
