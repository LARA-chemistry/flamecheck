<template>
  <div class="oauth-callback-container">
    <n-card class="oauth-callback-card" size="small">
      <n-space vertical align="center" class="oauth-inner">
        <template v-if="!failed">
          <n-spin size="large" />
          <p class="oauth-msg">Completing your sign-in…</p>
        </template>
        <template v-else>
          <n-alert type="error" title="Sign-in did not complete">
            {{ error }}
          </n-alert>
          <n-button type="primary" @click="router.push({ name: 'login' })">Back to sign in</n-button>
        </template>
      </n-space>
    </n-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { homeForRole } from '../router'
import { api } from '../api/client'
import { NCard, NSpace, NButton, NAlert, NSpin } from 'naive-ui'

const router = useRouter()
const auth = useAuthStore()
const failed = ref(false)
const error = ref('')

// After allauth completes the OAuth sign-in the browser lands here with a
// Django session. Exchange that session for the JWT the SPA uses, then route.
async function exchange() {
  try {
    const res = await api.post('/auth/oauth/exchange', {})
    const tokens = res.tokens ?? {}
    auth.setTokens(tokens.access, tokens.refresh)
    auth.setUser(res.user ?? (await api.get('/me')))
    if (auth.user?.role === 'student' && auth.user?.onboarded === false) {
      router.replace({ name: 'onboarding' })
    } else {
      router.replace({ name: homeForRole(auth.user?.role) })
    }
  } catch (e) {
    failed.value = true
    error.value =
      e.message || 'Your sign-in session was not found. Please try signing in again.'
  }
}

onMounted(exchange)
</script>

<style scoped>
.oauth-callback-container {
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
.oauth-callback-card {
  width: 100%;
  max-width: 420px;
  background: rgba(255, 255, 255, 0.96);
  border-radius: var(--fc-radius-lg);
}
.oauth-inner {
  padding: var(--fc-space-lg) 0;
}
.oauth-msg {
  margin: var(--fc-space-sm) 0 0;
  font-size: var(--fc-fs-sm);
  color: var(--fc-muted);
}
</style>
