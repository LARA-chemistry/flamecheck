<template>
  <div class="fc-page">
    <header class="fc-header landing-header">
      <div class="landing-brand">
        <img class="landing-logo" :src="logo" alt="FlameCheck logo" />
        <div>
          <h1 class="fc-title fc-title--hero">FlameCheck</h1>
          <p class="landing-subtitle">Your flame test analyses</p>
        </div>
      </div>
      <div class="landing-actions">
        <span class="fc-user" v-if="user">
          <span class="fc-user__avatar">{{ initial(user) }}</span>
          <span class="fc-user__name">{{ user.name || user.username }}</span>
        </span>
        <n-button size="small" secondary @click="handleLogout">Logout</n-button>
      </div>
    </header>

    <n-spin :show="loading">
      <n-empty v-if="!loading && analyses.length === 0" class="empty" description="No analyses assigned yet." />
      <div v-else class="fc-card-grid">
        <div
          v-for="a in analyses"
          :key="a.id"
          class="fc-card"
          :class="isActive(a) ? 'fc-card--interactive' : 'fc-card--inactive'"
          role="button"
          :tabindex="isActive(a) ? 0 : -1"
          :aria-label="`Open ${a.type} number ${a.number}`"
          :aria-disabled="String(!isActive(a))"
          @click="openAnalysis(a)"
          @keyup.enter="openAnalysis(a)"
        >
          <span class="fc-card__accent" :class="{ 'fc-card__accent--muted': !isActive(a) }"></span>
          <div class="analysis-card">
            <div class="analysis-card__top">
              <span class="analysis-card__num">#{{ a.number }}</span>
              <n-tag :type="windowTagType(a.window_status)" round size="small">
                {{ windowLabel(a.window_status) }}
              </n-tag>
            </div>
            <h3 class="analysis-card__title">{{ a.type }}</h3>
            <div class="analysis-card__stats">
              <div class="stat">
                <span class="stat__value">{{ a.score != null ? a.score : '—' }}</span>
                <span class="stat__label">points</span>
              </div>
              <div class="stat">
                <span class="stat__value">{{ a.submission_count }}/{{ a.submission_limit }}</span>
                <span class="stat__label">submissions</span>
              </div>
            </div>
            <n-button
              class="analysis-card__action"
              type="primary"
              secondary
              block
              :disabled="a.window_status !== 'open' && a.window_status !== 'submitted'"
              @click.stop="openAnalysis(a)"
            >
              {{ a.window_status === 'submitted' ? 'View Result' : 'Open Analysis' }}
            </n-button>
          </div>
        </div>
      </div>
    </n-spin>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { api } from '../api/client'
import logo from '../assets/flamecheck-logo.svg'
import { NSpin, NEmpty, NTag, NButton } from 'naive-ui'

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
function initial(u) {
  return ((u?.name || u?.username) || '?').trim().charAt(0).toUpperCase()
}
// An analysis is actionable only while its window is open or already submitted.
// too_early / too_late analyses are shown greyed-out and are not clickable.
function isActive(a) {
  return a.window_status === 'open' || a.window_status === 'submitted'
}
function openAnalysis(a) {
  if (isActive(a)) {
    router.push(`/analysis/${a.id}`)
  }
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
.landing-header {
  align-items: flex-start;
}

.landing-brand {
  display: flex;
  align-items: center;
  gap: var(--fc-space-sm);
}

.landing-logo {
  width: clamp(48px, 7vw, 72px);
  height: clamp(48px, 7vw, 72px);
  border-radius: 16px;
  box-shadow: var(--fc-shadow);
  flex-shrink: 0;
}

.landing-subtitle {
  color: var(--fc-text-soft);
  font-size: var(--fc-fs-sm);
  margin-top: 2px;
}

.landing-actions {
  display: flex;
  align-items: center;
  gap: var(--fc-space-xs);
}

.fc-user__name {
  max-width: 40vw;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (min-width: 900px) {
  .fc-user__name {
    max-width: none;
  }
}

.empty {
  padding: var(--fc-space-lg) 0;
  text-align: center;
}

.analysis-card {
  padding: var(--fc-space-sm);
  padding-top: calc(var(--fc-space-sm) + 4px);
  display: flex;
  flex-direction: column;
  gap: var(--fc-space-xs);
  flex: 1 1 auto;
  min-height: 0;
}

.analysis-card__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.analysis-card__num {
  font-weight: 800;
  font-size: var(--fc-fs-md);
  color: var(--fc-flame-2);
}

.analysis-card__title {
  font-size: var(--fc-fs-md);
  font-weight: 700;
  color: var(--fc-ink);
  line-height: 1.25;
}

.analysis-card__stats {
  display: flex;
  gap: var(--fc-space-md);
  padding: var(--fc-space-xs) var(--fc-space-sm);
  background: var(--fc-flame-soft);
  border-radius: var(--fc-radius-sm);
  margin-top: auto;
}

.stat {
  display: flex;
  flex-direction: column;
}

.stat__value {
  font-size: var(--fc-fs-md);
  font-weight: 800;
  color: var(--fc-ink);
  line-height: 1.1;
}

.stat__label {
  font-size: var(--fc-fs-xs);
  color: var(--fc-text-soft);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.analysis-card__action {
  margin-top: var(--fc-space-xs);
}

/* Inactive (not yet open / closed) analyses: greyed out and not interactive. */
.fc-card--inactive {
  cursor: default;
  opacity: 0.62;
  filter: grayscale(0.55);
  box-shadow: var(--fc-shadow-sm);
}
.fc-card--inactive:hover,
.fc-card--inactive:focus-within {
  transform: none;
  box-shadow: var(--fc-shadow-sm);
}
.fc-card--inactive .analysis-card__num,
.fc-card--inactive .analysis-card__title {
  color: var(--fc-muted);
}
.fc-card--inactive .analysis-card__stats {
  background: rgba(127, 127, 127, 0.12);
}
.fc-card--inactive .stat__value {
  color: var(--fc-text-soft);
}
.fc-card__accent--muted {
  background: var(--fc-border) !important;
}
</style>
