<template>
  <div class="login-container">
    <div class="login-box">
      <div class="login-header">
        <h2>🌍 Dplight ERP</h2>
        <p>Enterprise Resource Planning System</p>
      </div>
      <a-form :model="form" @submit="handleSubmit" layout="vertical">
        <a-form-item field="username" label="Username">
          <a-input v-model="form.username" placeholder="Enter username" allow-clear>
            <template #prefix>
              <icon-user />
            </template>
          </a-input>
        </a-form-item>
        <a-form-item field="password" label="Password">
          <a-input-password v-model="form.password" placeholder="Enter password" allow-clear>
            <template #prefix>
              <icon-lock />
            </template>
          </a-input-password>
        </a-form-item>
        <a-form-item>
          <a-button type="primary" html-type="submit" long :loading="loading">
            Login
          </a-button>
        </a-form-item>
      </a-form>
      <div class="login-footer">
        <p>Default Accounts:</p>
        <div class="accounts">
          <span>boss888 (Superuser)</span>
          <span>ug888, (Uganda)</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { Message } from '@arco-design/web-vue'
import { IconUser, IconLock } from '@arco-design/web-vue/es/icon'
import api from '@/api'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const loading = ref(false)
const form = reactive({
  username: '',
  password: ''
})

const handleSubmit = async () => {
  if (!form.username || !form.password) {
    Message.warning('Please enter username and password')
    return
  }

  loading.value = true
  try {
    // Call login API
    const formData = new FormData()
    formData.append('username', form.username)
    formData.append('password', form.password)
    
    const response = await api.post('/auth/login', formData)
    const { access_token } = response.data
    
    // Decode token to get user info (or use a separate /me endpoint)
    // For now, we'll simulate it or decode it if we had a jwt library
    // But better to fetch user info from backend
    // Or simpler: let backend return user info in login response? 
    // The current backend returns just token.
    // Let's assume we can get user info from token payload or another call.
    // For simplicity, we'll decode the base64 payload here manually.
    
    const payload = JSON.parse(atob(access_token.split('.')[1]))
    
    authStore.login(
      access_token,
      payload.sub,
      [payload.role],
      payload.allowed_companies,
      payload.is_superuser
    )
    
    Message.success('Login successful')
    const redirect = route.query.redirect as string || '/'
    router.push(redirect)
    
  } catch (error: any) {
    Message.error(error.response?.data?.detail || 'Login failed')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped lang="less">
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background-color: #f0f2f5;
  background-image: url('https://gw.alipayobjects.com/zos/rmsportal/TVYTbAXWheQpRcWDaDMu.svg');
  background-repeat: no-repeat;
  background-position: center 110px;
  background-size: 100%;
}

.login-box {
  width: 400px;
  padding: 40px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
  
  h2 {
    margin: 0;
    color: #1890ff;
    font-size: 24px;
  }
  
  p {
    margin: 8px 0 0;
    color: #8c8c8c;
  }
}

.login-footer {
  margin-top: 24px;
  text-align: center;
  font-size: 12px;
  color: #8c8c8c;
  
  .accounts {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-top: 8px;
  }
}
</style>