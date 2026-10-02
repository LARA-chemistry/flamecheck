<template>
  <div class="fc-page">
    <p v-if="user?.course_name" class="page-course">{{ user.course_name }}</p>
    <header class="fc-header landing-header">
      <div class="landing-brand">
        <img class="landing-logo" :src="logo" alt="FlameCheck logo" />
        <!-- Mobile only: the course name sits right next to the (minimised) logo. -->
        <span v-if="user?.course_name" class="landing-course-inline">{{ user.course_name }}</span>
        <div class="landing-titles">
          <h1 class="fc-title fc-title--hero">FlameCheck</h1>
          <p class="landing-subtitle">Your flame test analyses</p>
        </div>
      </div>
      <div class="landing-actions">
        <span class="fc-user" v-if="user">
          <span class="fc-user__avatar">{{ initial(user) }}</span>
          <span class="fc-user__meta">
            <span class="fc-user__name">{{ user.name || user.username }}</span>
            <span v-if="user.matriculation_no" class="fc-user__matric">Mat. {{ user.matriculation_no }}</span>
          </span>
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
            <p v-if="windowInterval(a)" class="analysis-card__window" :title="windowInterval(a)">
              <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true" class="analysis-card__window-icon">
                <rect x="3" y="4" width="18" height="17" rx="2" fill="none" stroke="currentColor" stroke-width="1.6" />
                <path d="M3 9h18M8 2v4M16 2v4" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
              </svg>
              {{ windowInterval(a) }}
            </p>
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
// Format the active window as a compact "date — date" interval (e.g.
// "01 Oct 13:00 – 15:00", or a full range across days). Returns '' if the
// window times are missing.
function windowInterval(a) {
  if (!a?.window_start || !a?.window_end) return ''
  const start = new Date(a.window_start)
  const end = new Date(a.window_end)
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return ''
  const optsDay = { day: '2-digit', month: 'short' }
  const optsFull = { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }
  const sameDay = start.toDateString() === end.toDateString()
  if (sameDay) {
    return `${start.toLocaleDateString(undefined, optsDay)} · ${start.toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
    })} – ${end.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}`
  }
  return `${start.toLocaleDateString(undefined, optsFull)} – ${end.toLocaleDateString(undefined, optsFull)}`
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

/* The course name shown next to the logo — only on small screens (mobile).
   Hidden on desktop, where the course name lives at the top of the page. */
.landing-course-inline {
  display: none;
}

/* Course name sits at the very top of the page, above the brand — plain bold
   text, no frame or background, at the (former) course-tag size. */
.page-course {
  margin: 0;
  padding: 0;
  font-size: var(--fc-fs-sm);
  font-weight: 700;
  color: var(--fc-ink);
  background: none;
  border: none;
}

/* --- Mobile: compact header ----------------------------------------------
   Shrink the logo to the top-left corner, drop the "FlameCheck" hero title
   and subtitle, and show the course name next to the logo instead. */
@media (max-width: 720px) {
  .page-course {
    display: none;
  }

  .landing-header {
    align-items: center;
    flex-wrap: nowrap;
    gap: var(--fc-space-xs);
    margin-bottom: var(--fc-space-sm);
  }

  .landing-brand {
    align-items: center;
    gap: var(--fc-space-xs);
    min-width: 0;
  }

  .landing-logo {
    width: 36px;
    height: 36px;
    border-radius: 10px;
  }

  .landing-titles {
    display: none;
  }

  .landing-course-inline {
    display: block;
    font-size: var(--fc-fs-sm);
    font-weight: 700;
    color: var(--fc-ink);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .landing-actions {
    margin-left: auto;
  }
}

.landing-actions {
  display: flex;
  align-items: center;
  gap: var(--fc-space-xs);
}

.fc-user__meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  line-height: 1.2;
}

.fc-user__name {
  max-width: 40vw;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 600;
}

.fc-user__matric {
  font-size: var(--fc-fs-xs);
  color: var(--fc-text-soft);
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

.analysis-card__window {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0;
  font-size: var(--fc-fs-xs);
  color: var(--fc-text-soft);
  background: var(--fc-flame-soft);
  border-radius: var(--fc-radius-sm);
  padding: 5px 9px;
  min-width: 0;
}
.analysis-card__window-icon {
  flex-shrink: 0;
  color: var(--fc-flame-2);
}
.fc-card--inactive .analysis-card__window {
  background: rgba(127, 127, 127, 0.12);
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
