<template>
  <div class="page">
    <header class="header">
      <h1>FlameCheck</h1>
      <n-space>
        <n-tag size="small">{{ user?.name || user?.username }}</n-tag>
        <n-button size="small" quaternary @click="handleLogout">Logout</n-button>
      </n-space>
    </header>

    <n-card title="Your Analyses" size="large">
      <n-spin :show="loading">
        <n-empty v-if="!loading && analyses.length === 0" description="No analyses assigned yet." />
        <n-list v-else>
          <n-list-item v-for="a in analyses" :key="a.id">
            <n-thing size="small">
              <template #header>
                <n-space align="center" justify="space-between" style="width: 100%">
                  <span>
                    <strong>{{ a.type }}</strong> — #{{ a.number }}
                  </span>
                  <n-tag :type="windowTagType(a.window_status)" size="small">
                    {{ windowLabel(a.window_status) }}
                  </n-tag>
                </n-space>
              </template>
              <template #description>
                <n-space>
                  <n-text depth="3">
                    Score: {{ a.score != null ? a.score + ' pts' : '—' }}
                  </n-text>
                  <n-text depth="3">
                    Submissions: {{ a.submission_count }}/{{ a.submission_limit }}
                  </n-text>
                </n-space>
              </template>
              <template #footer>
                <n-button
                  size="small"
                  type="primary"
                  :disabled="a.window_status !== 'open' && a.window_status !== 'submitted'"
                  @click="router.push(`/analysis/${a.id}`)"
                >
                  {{ a.window_status === 'submitted' ? 'View Result' : 'Open Analysis' }}
                </n-button>
              </template>
            </n-thing>
          </n-list-item>
        </n-list>
      </n-spin>
    </n-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { api } from '../api/client'
import {
  NCard, NSpin, NEmpty, NList, NListItem, NThing, NSpace, NText,
  NButton, NTag,
} from 'naive-ui'

const router = useRouter()
const auth = useAuthStore()
const user = auth.user
const loading = ref(true)
const analyses = ref([])

function windowTagType(status) {
  const map = { open: 'success', too_early: 'warning', too_late: 'error', submitted: 'info' }
  return map[status] || 'default'
}
function windowLabel(status) {
  const map = { open: 'Open', too_early: 'Not Open Yet', too_late: 'Closed', submitted: 'Submitted' }
  return map[status] || status
}

async function load() {
  loading.value = true
  try {
    analyses.value = await api.get('/analyses')
  } finally {
    loading.value = false
  }
}

function handleLogout() {
  auth.logout()
  router.push('/login')
}

onMounted(load)
</script>

<style scoped>
.page {
  max-width: 900px;
  margin: 0 auto;
  padding: 24px;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}
</style>
