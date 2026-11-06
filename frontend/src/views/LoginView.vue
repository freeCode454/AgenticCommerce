<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import client from '@/api/client'
import { errorMessage, statusCode } from '@/utils/format'
import type { ApiResponse, UserInfo } from '@/types'
import AppIcon from '@/components/ui/AppIcon.vue'
import BrandLogo from '@/components/ui/BrandLogo.vue'
import BrandScene from '@/components/ui/BrandScene.vue'
const route = useRoute(),
  router = useRouter(),
  user = useUserStore()
const email = ref(localStorage.getItem('remembered-email') || ''),
  password = ref(''),
  remember = ref(!!email.value),
  visible = ref(false),
  loading = ref(false),
  error = ref('')
async function login() {
  if (loading.value) return
  error.value = ''
  loading.value = true
  try {
    const response = await client.post<ApiResponse<{ access_token: string; user: UserInfo }>>(
      '/auth/login',
      { email: email.value.trim(), password: password.value },
    )
    if (!response.data.data.access_token) throw new Error('Missing access token')
    if (remember.value) localStorage.setItem('remembered-email', email.value.trim())
    else localStorage.removeItem('remembered-email')
    user.setToken(response.data.data.access_token)
    const target = typeof route.query.redirect === 'string' ? route.query.redirect : '/dashboard'
    const safe =
      target.startsWith('/') &&
      !target.startsWith('//') &&
      !target.startsWith('/login') &&
      router.resolve(target).matched.some((record) => record.path !== '/:pathMatch(.*)*')
    await router.replace(safe ? target : '/dashboard')
  } catch (cause) {
    error.value =
      statusCode(cause) === 401
        ? '邮箱或密码不正确，请核对后重试。'
        : errorMessage(cause, '登录未完成，请检查邮箱和密码后重试。')
  } finally {
    loading.value = false
  }
}
</script>
<template>
  <main class="login-page">
    <section class="login-story">
      <BrandLogo />
      <div class="story-heading">
        <span class="story-kicker">
          <i />
          品牌内容，有了新的可能
        </span>
        <h1>
          下一站，
          <br />
          让好商品被看见
          <span>。</span>
        </h1>
        <p>
          从灵感到交付前的每一步，
          <br />
          让 AI 成为你的品牌创作伙伴。
        </p>
      </div>
      <BrandScene />
      <footer class="story-footer">
        <span>商品 × 品牌 × AI</span>
        <span>更好的表达，更多的可能。</span>
      </footer>
    </section>
    <section class="login-form-side">
      <div class="login-form-wrap">
        <span class="welcome-mark"><AppIcon name="spark" :size="26" /></span>
        <span class="overline">WELCOME BACK</span>
        <h2>欢迎回到创作现场</h2>
        <p class="login-subtitle">登录你的工作空间，让下一个好创意发生。</p>
        <form @submit.prevent="login" :aria-busy="loading">
          <label for="login-email">工作邮箱</label>
          <div class="login-input">
            <AppIcon name="mail" :size="18" />
            <input
              id="login-email"
              v-model="email"
              type="email"
              required
              autocomplete="username"
              placeholder="you@company.com"
              :disabled="loading"
              autofocus
            />
          </div>
          <label for="login-password">登录密码</label>
          <div class="login-input">
            <AppIcon name="lock" :size="18" />
            <input
              id="login-password"
              v-model="password"
              :type="visible ? 'text' : 'password'"
              required
              autocomplete="current-password"
              placeholder="输入你的密码"
              :disabled="loading"
            />
            <button
              type="button"
              class="icon-button"
              :aria-label="visible ? '隐藏密码' : '显示密码'"
              :aria-pressed="visible"
              @click="visible = !visible"
            >
              <AppIcon name="eye" :size="18" />
            </button>
          </div>
          <div class="login-options">
            <label class="checkbox-label">
              <input v-model="remember" type="checkbox" />
              记住邮箱
            </label>
            <span>
              <AppIcon name="shield" :size="15" />
              企业工作空间
            </span>
          </div>
          <p v-if="error" class="form-error" role="alert">{{ error }}</p>
          <button class="btn btn-primary login-submit" type="submit" :disabled="loading">
            <span v-if="loading" class="spinner" />
            {{ loading ? '正在登录…' : '登录工作空间' }}
            <AppIcon v-if="!loading" name="arrow-right" :size="18" />
          </button>
        </form>
        <p class="login-help">
          还没有访问权限？
          <strong>请联系你的企业管理员</strong>
        </p>
        <p class="login-security">
          <AppIcon name="shield" :size="16" />
          在你的企业工作空间中管理品牌资产与内容。
        </p>
      </div>
      <footer class="login-copyright">© 2026 AgenticCommerce</footer>
    </section>
  </main>
</template>
