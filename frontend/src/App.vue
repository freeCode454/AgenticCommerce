<script setup lang="ts">
import { computed, ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { navigation } from '@/config/navigation'
import AppIcon from '@/components/ui/AppIcon.vue'
import BrandLogo from '@/components/ui/BrandLogo.vue'
import AppDialog from '@/components/ui/AppDialog.vue'
import UiHost from '@/components/ui/UiHost.vue'
const route = useRoute(),
  router = useRouter(),
  user = useUserStore()
const isLogin = computed(() => route.path === '/login')
const mobileOpen = ref(false),
  searchOpen = ref(false),
  query = ref(''),
  selected = ref(0)
const compact = ref(window.innerWidth < 1024),
  sidebar = ref<HTMLElement>(),
  accountMenu = ref<HTMLDetailsElement>()
let priorFocus: HTMLElement | null = null
function resize() {
  compact.value = window.innerWidth < 1024
  if (!compact.value) mobileOpen.value = false
}
const links = computed(() =>
  navigation.filter((item) => !item.admin || user.userInfo?.role === 'admin'),
)
const groups = computed(() =>
  ['工作空间', '内容资产', '品牌与管理'].map((title) => ({
    title,
    items: links.value.filter((item) => item.group === title),
  })),
)
const results = computed(() =>
  links.value.filter((item) => item.title.toLowerCase().includes(query.value.trim().toLowerCase())),
)
const initial = computed(() => user.userInfo?.name?.slice(0, 1) || 'A')
const roleLabel = computed(() =>
  user.userInfo?.role === 'admin' ? '管理员' : user.userInfo ? '工作空间成员' : '正在获取身份',
)
function closeAccount(restoreFocus = false) {
  const focusedInside = accountMenu.value?.contains(document.activeElement)
  accountMenu.value?.removeAttribute('open')
  if (restoreFocus && focusedInside) accountMenu.value?.querySelector('summary')?.focus()
}
function outsideAccount(event: PointerEvent) {
  if (event.target instanceof Node && !accountMenu.value?.contains(event.target)) closeAccount()
}
function logout() {
  closeAccount()
  user.clearToken()
  void router.replace('/login')
}
function openSearch() {
  closeAccount(true)
  query.value = ''
  selected.value = 0
  searchOpen.value = true
}
function accountFocusOut(event: FocusEvent) {
  // focusout fires before the next element becomes document.activeElement.
  if (event.relatedTarget instanceof Node) {
    if (!accountMenu.value?.contains(event.relatedTarget)) closeAccount()
  } else {
    setTimeout(() => {
      if (!accountMenu.value?.contains(document.activeElement)) closeAccount()
    }, 0)
  }
}
function navigate(index: number) {
  const item = results.value[index]
  if (item) {
    searchOpen.value = false
    void router.push(item.path)
  }
}
function keydown(event: KeyboardEvent) {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k' && !isLogin.value) {
    event.preventDefault()
    mobileOpen.value = false
    searchOpen.value ? (searchOpen.value = false) : openSearch()
  }
  if (event.key === 'Escape') {
    mobileOpen.value = false
    if (accountMenu.value?.open) {
      closeAccount()
      accountMenu.value.querySelector('summary')?.focus()
    }
  }
  if (event.key === 'Tab' && mobileOpen.value) {
    const targets = Array.from(
      sidebar.value?.querySelectorAll<HTMLElement>('a,button:not(:disabled)') || [],
    )
    const first = targets[0],
      last = targets[targets.length - 1]
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last?.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first?.focus()
    }
  }
}
function moveSearch(delta: number) {
  if (results.value.length)
    selected.value = (selected.value + delta + results.value.length) % results.value.length
}
watch(query, () => (selected.value = 0))
watch(
  () => route.fullPath,
  () => {
    mobileOpen.value = false
    searchOpen.value = false
    closeAccount()
  },
)
watch(mobileOpen, async (value) => {
  document.body.classList.toggle('navigation-open', value)
  if (value) {
    priorFocus = document.activeElement as HTMLElement
    await nextTick()
    sidebar.value?.querySelector<HTMLElement>('a')?.focus()
  } else {
    await nextTick()
    if (priorFocus?.isConnected) priorFocus.focus()
  }
})
onMounted(() => {
  window.addEventListener('keydown', keydown)
  window.addEventListener('resize', resize)
  document.addEventListener('pointerdown', outsideAccount)
})
onUnmounted(() => {
  window.removeEventListener('keydown', keydown)
  window.removeEventListener('resize', resize)
  document.removeEventListener('pointerdown', outsideAccount)
  document.body.classList.remove('navigation-open')
})
</script>
<template>
  <RouterView v-if="isLogin" />
  <div v-else class="app-layout">
    <a class="skip-link" href="#main-content">跳转到页面内容</a>
    <button
      v-if="mobileOpen"
      class="sidebar-overlay"
      aria-label="关闭导航"
      @click="mobileOpen = false"
    />
    <aside
      ref="sidebar"
      class="sidebar"
      :class="{ 'sidebar-open': mobileOpen }"
      aria-label="工作空间导航"
      :inert="compact && !mobileOpen"
    >
      <RouterLink to="/dashboard" class="brand-link" aria-label="AgenticCommerce 工作台">
        <BrandLogo />
      </RouterLink>
      <div class="organization">
        <span class="organization-symbol"><AppIcon name="box" :size="19" /></span>
        <div>
          <strong :title="user.userInfo?.tenant_name">
            {{ user.userInfo?.tenant_name || '当前工作空间' }}
          </strong>
          <small>当前工作空间</small>
        </div>
      </div>
      <nav class="sidebar-nav">
        <section v-for="group in groups" :key="group.title">
          <h2>{{ group.title }}</h2>
          <RouterLink
            v-for="item in group.items"
            :key="item.path"
            :to="item.path"
            class="nav-item"
            :class="{
              'nav-active':
                route.path === item.path ||
                (item.path === '/tasks' && route.path.startsWith('/workbench/')),
            }"
          >
            <AppIcon :name="item.icon" :size="18" />
            <span>{{ item.title }}</span>
          </RouterLink>
        </section>
      </nav>
      <div class="sidebar-profile">
        <span class="avatar">{{ initial }}</span>
        <div>
          <strong :title="user.userInfo?.name">{{ user.userInfo?.name || '已登录用户' }}</strong>
          <small>{{ roleLabel }}</small>
        </div>
        <button class="icon-button" aria-label="退出登录" title="退出登录" @click="logout">
          <AppIcon name="logout" :size="18" />
        </button>
      </div>
    </aside>
    <div class="main-wrapper" :inert="compact && mobileOpen">
      <header class="app-header">
        <div class="breadcrumb">
          <button
            class="icon-button mobile-menu"
            aria-label="打开导航"
            :aria-expanded="mobileOpen"
            @click="mobileOpen = true"
          >
            <AppIcon name="menu" />
          </button>
          <span>{{ route.meta.group || '工作空间' }}</span>
          <AppIcon name="chevron-right" :size="13" />
          <strong>{{ route.meta.title }}</strong>
        </div>
        <div class="header-actions">
          <button class="search-trigger" aria-label="搜索功能页面" @click="openSearch">
            <AppIcon name="search" :size="17" />
            <span>搜索功能页面</span>
            <kbd>Ctrl K</kbd>
          </button>
          <details ref="accountMenu" class="account-menu" @focusout="accountFocusOut">
            <summary aria-label="查看当前账号" :title="user.userInfo?.name">
              <span class="mini-avatar">{{ initial }}</span>
              <span class="header-user">
                <strong>{{ user.userInfo?.name || '已登录用户' }}</strong>
                <small>{{ roleLabel }}</small>
              </span>
              <AppIcon name="chevron-down" :size="14" />
            </summary>
            <div class="account-popover" role="group" aria-label="当前账号信息">
              <strong>{{ user.userInfo?.name || '已登录用户' }}</strong>
              <p>{{ user.userInfo?.email || '正在获取邮箱' }}</p>
              <p class="account-workspace">{{ user.userInfo?.tenant_name || '当前工作空间' }}</p>
              <RouterLink to="/settings">
                <AppIcon name="settings" :size="16" />
                工作空间设置
              </RouterLink>
              <button @click="logout">
                <AppIcon name="logout" :size="16" />
                退出登录
              </button>
            </div>
          </details>
        </div>
      </header>
      <main id="main-content" class="page-content" tabindex="-1">
        <div v-if="user.identityError" class="notice notice-warning" role="alert">
          <AppIcon name="warning" />
          <span>无法获取当前身份：{{ user.identityError }}</span>
          <button class="text-button" @click="user.fetchUser().catch(() => {})">重试</button>
        </div>
        <RouterView />
      </main>
      <footer class="app-footer">
        <span>AGENTICCOMMERCE</span>
        <span>让每一个好商品，都有好的表达。</span>
      </footer>
    </div>
  </div>
  <AppDialog
    v-model="searchOpen"
    title="快速前往"
    description="搜索页面名称，使用方向键选择，按 Enter 打开。"
  >
    <div class="search-input">
      <AppIcon name="search" />
      <input
        v-model="query"
        autofocus
        aria-label="搜索功能页面"
        placeholder="你想前往哪里？"
        @keydown.down.prevent="moveSearch(1)"
        @keydown.up.prevent="moveSearch(-1)"
        @keydown.enter.prevent="navigate(selected)"
      />
    </div>
    <div class="command-results">
      <button
        v-for="(item, index) in results"
        :key="item.path"
        class="command-result"
        :class="{ 'command-selected': selected === index }"
        @click="navigate(index)"
      >
        <AppIcon :name="item.icon" />
        <span>{{ item.title }}</span>
        <AppIcon name="arrow-right" :size="16" />
      </button>
      <p v-if="!results.length" class="muted center padded">没有找到相关页面，请换个关键词。</p>
    </div>
  </AppDialog>
  <UiHost />
</template>
