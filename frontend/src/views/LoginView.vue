<template>
  <div class="login-card card">
    <div class="login-brand">
      <span class="brand-icon">⚡</span>
      <h2 class="brand-title">AgenticCommerce</h2>
      <p class="brand-sub">自主智能体出海电商平台</p>
    </div>

    <form class="login-form mt-4" @submit.prevent="handleLogin">
      <div class="form-group">
        <label class="form-label">登录邮箱 (Email)</label>
        <input type="email" v-model="email" class="form-input" placeholder="admin@agentic.com" required />
      </div>

      <div class="form-group">
        <label class="form-label">密码 (Password)</label>
        <input type="password" v-model="password" class="form-input" placeholder="••••••••" required />
      </div>

      <button type="submit" class="btn btn-primary full-width mt-3" :disabled="loading">
        {{ loading ? '登录验证中...' : '立即登录' }}
      </button>

      <button type="button" class="btn btn-secondary full-width mt-2" @click="fillDemoAccount">
        ⚡ 一键填入系统管理员演示账号
      </button>
    </form>

    <div class="login-footer mt-4">
      <span class="text-xs text-light">飞流智能科技 × 环球出海科技有限公司</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import client from '@/api/client'

const router = useRouter()
const userStore = useUserStore()

const email = ref('admin@agentic.com')
const password = ref('admin123')
const loading = ref(false)

function fillDemoAccount() {
  email.value = 'admin@agentic.com'
  password.value = 'admin123'
}

async function handleLogin() {
  loading.value = true
  try {
    const res = await client.post('/auth/login', {
      email: email.value,
      password: password.value
    })
    const token = res.data?.data?.access_token
    if (token) {
      userStore.setToken(token)
      alert('登录成功！欢迎进入 AgenticCommerce 自主智能体平台。')
      router.push('/dashboard')
    }
  } catch (e: any) {
    alert(e.response?.data?.detail || '登录失败，请检查账号密码')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-card {
  width: 100%;
  max-width: 420px;
  padding: 32px;
  background: #ffffff;
  border-radius: 16px;
  box-shadow: 0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1);
}

.login-brand {
  text-align: center;
}
.brand-icon {
  font-size: 36px;
  background: #eef2ff;
  border-radius: 12px;
  padding: 8px;
  display: inline-block;
  margin-bottom: 8px;
}
.brand-title {
  font-size: 20px;
  font-weight: 700;
  color: #0f172a;
}
.brand-sub {
  font-size: 13px;
  color: #64748b;
  margin-top: 2px;
}

.full-width {
  width: 100%;
}
.login-footer {
  text-align: center;
  border-top: 1px solid var(--border);
  padding-top: 14px;
}
</style>
