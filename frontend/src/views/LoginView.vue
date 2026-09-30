<template>
  <div class="login-container">
    <n-card class="login-card" title="FlameCheck" size="large">
      <n-form ref="formRef" :model="form" :rules="rules" label-placement="left">
        <n-form-item label="Username" path="username">
          <n-input v-model:value="form.username" placeholder="Enter username" />
        </n-form-item>
        <n-form-item label="Password" path="password">
          <n-input
            v-model:value="form.password"
            type="password"
            show-password
            placeholder="Enter password"
          />
        </n-form-item>
        <n-button type="primary" block :loading="loading" @click="handleLogin">
          Sign In
        </n-button>
      </n-form>
      <n-alert v-if="error" type="error" style="margin-top: 12px">{{ error }}</n-alert>
    </n-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { homeForRole } from '../router'
import { NCard, NForm, NFormItem, NInput, NButton, NAlert } from 'naive-ui'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const error = ref('')

const form = ref({ username: '', password: '' })
const rules = {
  username: { required: true, message: 'Username is required', trigger: 'blur' },
  password: { required: true, message: 'Password is required', trigger: 'blur' },
}
const formRef = ref(null)

async function handleLogin() {
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  loading.value = true
  error.value = ''
  try {
    await auth.login(form.value.username, form.value.password)
    router.push({ name: homeForRole(auth.user?.role) })
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
.login-card {
  width: 420px;
  border-radius: 12px;
}
</style>
