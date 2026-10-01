<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-brand">
        <img class="login-logo" :src="logo" alt="FlameCheck logo" />
        <div class="login-brand__text">
          <h1 class="login-title">FlameCheck</h1>
          <p class="login-subtitle">Flame test analysis &amp; grading</p>
        </div>
      </div>

      <n-form ref="formRef" :model="form" :rules="rules" label-placement="top" class="login-form">
        <n-form-item label="Username" path="username">
          <n-input
            v-model:value="form.username"
            placeholder="Enter username"
            size="large"
            clearable
            @keyup.enter="handleLogin"
          />
        </n-form-item>
        <n-form-item label="Password" path="password">
          <n-input
            v-model:value="form.password"
            :type="showPassword ? 'text' : 'password'"
            size="large"
            placeholder="Enter password"
            @keyup.enter="handleLogin"
          >
            <template #suffix>
              <button
                type="button"
                class="pw-toggle"
                :aria-label="showPassword ? 'Hide password' : 'Show password'"
                :aria-pressed="String(showPassword)"
                title="Show / hide password"
                tabindex="-1"
                @click="showPassword = !showPassword"
              >
                <!-- Eye (password hidden) -->
                <svg v-if="!showPassword" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
                  <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" />
                  <circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" stroke-width="1.6" />
                </svg>
                <!-- Eye with slash (password visible) -->
                <svg v-else viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
                  <path d="M3 3l18 18" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
                  <path d="M10.6 5.1A9.7 9.7 0 0 1 12 5c6.5 0 10 7 10 7a17 17 0 0 1-3.2 3.9M6.6 6.6C3.9 8.2 2 12 2 12s3.5 7 10 7a9.5 9.5 0 0 0 4.2-1" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
                  <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
                </svg>
              </button>
            </template>
          </n-input>
        </n-form-item>
        <n-button type="primary" size="large" block :loading="loading" class="login-submit" @click="handleLogin">
          Sign In
        </n-button>
      </n-form>

      <n-alert v-if="error" type="error" class="login-error">{{ error }}</n-alert>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { homeForRole } from '../router'
import logo from '../assets/flamecheck-logo.svg'
import { NForm, NFormItem, NInput, NButton, NAlert } from 'naive-ui'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const error = ref('')

const form = ref({ username: '', password: '' })
const showPassword = ref(false)
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
  min-height: 100dvh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--fc-space-sm);
  position: relative;
  overflow: hidden;
  /* Flame gradient: deep navy base with a warm flame glow rising from the base. */
  background:
    radial-gradient(120% 90% at 50% 118%, rgba(255, 138, 0, 0.55) 0%, rgba(229, 57, 53, 0.28) 32%, transparent 60%),
    radial-gradient(90% 70% at 82% 8%, rgba(255, 213, 74, 0.28) 0%, transparent 55%),
    linear-gradient(160deg, #0d1b2a 0%, #12233a 48%, #3a1f1a 100%);
}

/* Subtle animated flame shimmer. */
.login-container::after {
  content: '';
  position: absolute;
  inset: auto 0 0 0;
  height: 45%;
  background: radial-gradient(60% 100% at 50% 100%, rgba(255, 176, 32, 0.22), transparent 70%);
  filter: blur(6px);
  animation: fc-flicker 4.5s ease-in-out infinite;
  pointer-events: none;
}

@keyframes fc-flicker {
  0%, 100% { opacity: 0.55; transform: scaleY(1); }
  50% { opacity: 0.85; transform: scaleY(1.08); }
}

@media (prefers-reduced-motion: reduce) {
  .login-container::after { animation: none; }
}

.login-card {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 440px;
  background: rgba(255, 255, 255, 0.96);
  backdrop-filter: blur(10px);
  border-radius: var(--fc-radius-lg);
  border: 1px solid rgba(255, 255, 255, 0.4);
  box-shadow: var(--fc-shadow-lift);
  padding: var(--fc-space-md);
  margin: var(--fc-space-md) 0;
}

@media (min-width: 620px) {
  .login-card {
    padding: var(--fc-space-lg) var(--fc-space-md) var(--fc-space-md);
    margin: 0;
  }
}

.login-brand {
  display: flex;
  align-items: center;
  gap: var(--fc-space-sm);
  margin-bottom: var(--fc-space-md);
}

.login-logo {
  width: clamp(56px, 12vw, 76px);
  height: clamp(56px, 12vw, 76px);
  border-radius: 18px;
  box-shadow: var(--fc-shadow);
  flex-shrink: 0;
}

.login-title {
  font-size: var(--fc-fs-xl);
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1.1;
  background: var(--fc-flame-gradient);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: var(--fc-flame-2);
}

.login-subtitle {
  font-size: var(--fc-fs-sm);
  color: var(--fc-text-soft);
  margin-top: 2px;
}

.login-form {
  margin-top: var(--fc-space-xs);
}

.login-submit {
  margin-top: var(--fc-space-xs);
  font-weight: 700;
  letter-spacing: 0.01em;
}

.login-error {
  margin-top: var(--fc-space-sm);
}

/* Password show/hide eye toggle (input suffix). */
.pw-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: var(--fc-muted);
  cursor: pointer;
  padding: 2px;
  margin: 0;
  border-radius: 6px;
  line-height: 0;
  transition: color 0.15s ease, background 0.15s ease;
}
.pw-toggle:hover,
.pw-toggle:focus-visible {
  color: var(--fc-flame-2);
  outline: none;
}
</style>
