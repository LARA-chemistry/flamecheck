<template>
  <div class="register-container">
    <n-card class="register-card" size="small">
      <div class="register-head">
        <img class="register-logo" :src="logo" alt="FlameCheck" />
        <h1 class="register-title">Create your student account</h1>
        <p class="register-sub">
          Register for FlameCheck. You will receive a confirmation e-mail; your
          account becomes active once you confirm it.
        </p>
      </div>

      <n-alert v-if="done" type="success" class="register-done">
        Registration received — please check your e-mail for the confirmation link.
      </n-alert>

      <n-form
        v-show="!done"
        ref="formRef"
        :model="form"
        :rules="rules"
        label-placement="top"
        @keyup.enter="handleRegister"
      >
        <n-form-item label="First name" path="first_name">
          <n-input v-model:value="form.first_name" placeholder="First name" size="large" />
        </n-form-item>
        <n-form-item label="Last name" path="last_name">
          <n-input v-model:value="form.last_name" placeholder="Last name" size="large" />
        </n-form-item>
        <n-form-item label="E-mail" path="email">
          <n-input v-model:value="form.email" placeholder="you@institution.edu" size="large" />
        </n-form-item>
        <n-form-item label="Password" path="password">
          <n-input
            v-model:value="form.password"
            type="password"
            show-password-on="click"
            placeholder="Choose a password"
            size="large"
          />
        </n-form-item>
        <n-form-item label="Matriculation number (optional)" path="matriculation_no">
          <n-input v-model:value="form.matriculation_no" placeholder="e.g. M123456" size="large" />
        </n-form-item>
        <n-button type="primary" size="large" block :loading="loading" @click="handleRegister">
          Register
        </n-button>
      </n-form>

      <n-alert v-if="error" type="error" class="register-error">{{ error }}</n-alert>

      <p class="register-back">
        <router-link to="/login">← Back to sign in</router-link>
      </p>
    </n-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { api } from '../api/client'
import logo from '../assets/flamecheck-logo.svg'
import { NCard, NForm, NFormItem, NInput, NButton, NAlert } from 'naive-ui'

const loading = ref(false)
const error = ref('')
const done = ref(false)

const form = ref({
  first_name: '',
  last_name: '',
  email: '',
  password: '',
  matriculation_no: '',
})
const rules = {
  first_name: {
    validator(rule, value) {
      const hasAny = String(value || '').trim() || String(form.value.last_name || '').trim()
      return hasAny ? true : new Error('Enter a first or last name')
    },
    trigger: ['blur', 'input'],
  },
  email: {
    required: true,
    message: 'E-mail is required',
    trigger: 'blur',
    type: 'email',
  },
  password: { required: true, message: 'Password is required', trigger: 'blur' },
}
const formRef = ref(null)

async function handleRegister() {
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  loading.value = true
  error.value = ''
  try {
    await api.post('/auth/register', { ...form.value })
    done.value = true
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.register-container {
  min-height: 100vh;
  min-height: 100dvh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--fc-space-sm);
  background:
    radial-gradient(120% 90% at 50% 118%, rgba(255, 138, 0, 0.55) 0%, rgba(229, 57, 53, 0.28) 32%, transparent 60%),
    linear-gradient(160deg, #0d1b2a 0%, #12233a 48%, #3a1f1a 100%);
}
.register-card {
  width: 100%;
  max-width: 440px;
  background: rgba(255, 255, 255, 0.96);
  border-radius: var(--fc-radius-lg);
}
.register-head {
  text-align: center;
  margin-bottom: var(--fc-space-md);
}
.register-logo {
  width: 56px;
  height: auto;
}
.register-title {
  margin: var(--fc-space-xs) 0 4px;
  font-size: var(--fc-fs-lg);
  color: var(--fc-ink);
}
.register-sub {
  margin: 0;
  font-size: var(--fc-fs-sm);
  color: var(--fc-muted);
}
.register-done,
.register-error {
  margin-top: var(--fc-space-sm);
}
.register-back {
  margin: var(--fc-space-md) 0 0;
  text-align: center;
  font-size: var(--fc-fs-sm);
}
.register-back a {
  color: var(--fc-flame-2);
  font-weight: 600;
  text-decoration: none;
}
.register-back a:hover {
  text-decoration: underline;
}
</style>
