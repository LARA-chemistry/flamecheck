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
        <button
          class="fc-user fc-user--clickable"
          v-if="user"
          type="button"
          @click="profileShow = true"
          aria-haspopup="dialog"
        >
          <span class="fc-user__avatar">{{ initial(user) }}</span>
          <span class="fc-user__meta">
            <span class="fc-user__name">{{ user.full_name || user.username }}</span>
            <span v-if="user.matriculation_no" class="fc-user__matric">Mat. {{ user.matriculation_no }}</span>
            <span v-if="user.labspace_id" class="fc-user__labspace">Labspace {{ user.labspace_id }}</span>
          </span>
        </button>
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
          :role="isClickable(a) ? 'button' : undefined"
          :tabindex="isClickable(a) ? 0 : undefined"
          :aria-label="
            isClickable(a)
              ? canSubmit(a)
                ? `Open ${a.type} number ${a.number} to submit (${a.submission_count}/${a.submission_limit} used, ${windowLabel(displayStatus(a))})`
                : `View result for ${a.type} number ${a.number} (${windowLabel(displayStatus(a))})`
              : `${a.type} number ${a.number} (${windowLabel(displayStatus(a))}), no result yet`
          "
          @click="openAnalysis(a)"
          @keyup.enter="openAnalysis(a)"
        >
          <span class="fc-card__accent" :class="{ 'fc-card__accent--muted': !isActive(a) }"></span>
          <div class="analysis-card">
            <div class="analysis-card__top">
              <span class="analysis-card__num">#{{ a.number }}</span>
              <n-tag :type="windowTagType(displayStatus(a))" round size="small">
                {{ windowLabel(displayStatus(a)) }}
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
            <div class="analysis-card__actions">
              <n-button
                class="analysis-card__action"
                type="primary"
                secondary
                block
                :disabled="!canSubmit(a) && a.submission_count === 0"
                @click.stop="openAnalysis(a)"
              >
                {{ actionLabel(a) }}
              </n-button>
              <!-- Explicit results access, shown while the card click still
                   opens a new submission. -->
              <n-button
                v-if="canSubmit(a) && a.submission_count > 0"
                size="small"
                tertiary
                @click.stop="openResults(a)"
              >
                Results
              </n-button>
            </div>
          </div>
        </div>
      </div>
    </n-spin>

    <!-- Course-progress footer at the bottom of the page: a red-yellow-green
         bar (progress towards the max points, with a tick at the passing line)
         and the total/max points on the right, red until the course is passed. -->
    <footer v-if="summary && summary.ideal_score > 0" class="progress-dock">
      <div class="progress-dock__row">
        <div
          class="progress-dock__bar"
          role="progressbar"
          aria-valuemin="0"
          :aria-valuenow="summary.total_score"
          :aria-valuemax="summary.ideal_score"
          :aria-label="`Course progress: ${summary.total_score} of ${summary.ideal_score} points, ${summary.passing_score} required to pass`"
        >
          <div class="progress-dock__rest" :style="{ width: (100 - progressPct) + '%' }"></div>
          <span
            v-if="summary.passing_score > 0"
            class="progress-dock__marker"
            :style="{ left: passLinePct + '%' }"
            :title="`${summary.passing_score} points to pass`"
          ></span>
        </div>
        <span class="progress-dock__points" :class="{ 'progress-dock__points--passed': summary.passed }">
          {{ summary.total_score }} / {{ summary.ideal_score }}
        </span>
      </div>

      <!-- Course points summary, placed below the progress bar. -->
      <div class="course-summary">
        <div class="course-summary__stat">
          <span class="course-summary__value">{{ summary.total_score }}</span>
          <span class="course-summary__label">of {{ summary.ideal_score }} points</span>
        </div>
        <div class="course-summary__divider" aria-hidden="true"></div>
        <div class="course-summary__stat">
          <span class="course-summary__value">{{ summary.passing_score }}</span>
          <span class="course-summary__label">points to pass</span>
        </div>
        <div class="course-summary__divider" aria-hidden="true"></div>
        <n-tag :type="summary.passed ? 'success' : 'warning'" round size="small">
          {{ summary.passed ? 'Passed' : 'Not passed yet' }}
        </n-tag>
      </div>
    </footer>

    <ProfileModal v-model:show="profileShow" :user="user" :analyses="analyses" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { api } from '../api/client'
import logo from '../assets/flamecheck-logo.svg'
import ProfileModal from '../components/ProfileModal.vue'
import { NSpin, NEmpty, NTag, NButton } from 'naive-ui'

const router = useRouter()
const auth = useAuthStore()
const user = auth.user
const loading = ref(true)
const analyses = ref([])
// Course result (total/ideal/passing points + pass status) for the header bar.
const summary = ref(null)
// Profile modal visibility (toggled by clicking the user chip in the header).
const profileShow = ref(false)

// Progress-dock geometry: fill = total/max points (capped at 100%), and the
// tick marks where the passing line sits on the same 0..max scale.
const progressPct = computed(() => {
  const s = summary.value
  if (!s || !s.ideal_score) return 0
  return Math.min(100, Math.round((s.total_score / s.ideal_score) * 1000) / 10)
})
const passLinePct = computed(() => {
  const s = summary.value
  if (!s || !s.ideal_score || !s.passing_score) return 0
  return Math.min(100, Math.round((s.passing_score / s.ideal_score) * 1000) / 10)
})

function windowTagType(status) {
  const map = { open: 'success', too_early: 'warning', too_late: 'error', submitted: 'info' }
  return map[status] || 'default'
}
function windowLabel(status) {
  const map = { open: 'Open', too_early: 'Not Open Yet', too_late: 'Closed', submitted: 'Submitted' }
  return map[status] || status
}
// Format the analysis window as a compact, unambiguous interval. The start is
// always "day month · HH:MM"; the end adds its own date only when it falls on a
// different day (e.g. "01 Oct · 13:00 – 15:00" or
// "01 Oct · 08:00 – 05 Oct · 18:00"). Returns '' if either time is missing.
function windowInterval(a) {
  if (!a?.window_start || !a?.window_end) return ''
  const start = new Date(a.window_start)
  const end = new Date(a.window_end)
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return ''
  const day = (d) => d.toLocaleDateString(undefined, { day: '2-digit', month: 'short' })
  const time = (d) => d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
  const sameDay = start.toDateString() === end.toDateString()
  const startLabel = `${day(start)} · ${time(start)}`
  return sameDay ? `${startLabel} – ${time(end)}` : `${startLabel} – ${day(end)} · ${time(end)}`
}
function initial(u) {
  return ((u?.full_name || u?.username) || '?').trim().charAt(0).toUpperCase()
}
// Is the submission window still open right now? Derived from the raw window
// timestamps: the window_status payload already says "submitted" as soon as
// ANY submission exists, even while the window is still open and further
// submissions are possible.
function windowStillOpen(a) {
  if (!a?.window_start || !a?.window_end) return false
  const now = Date.now()
  return new Date(a.window_start).getTime() <= now && now <= new Date(a.window_end).getTime()
}
// A (further) submission is possible while the window is open and the limit
// has not been reached yet.
function canSubmit(a) {
  return windowStillOpen(a) && a.submission_count < a.submission_limit
}
// An analysis is shown (not greyed out) while it still accepts submissions or
// a submission already exists (a result to look at).
function isActive(a) {
  return canSubmit(a) || a.submission_count > 0
}
// Card tag: "Open" while (further) submissions are possible, "Submitted" once
// the window closed or the limit was reached, otherwise the raw window status.
function displayStatus(a) {
  if (a.submission_count > 0) return canSubmit(a) ? 'open' : 'submitted'
  return a.window_status
}
// A card can be opened when it still accepts a submission or when a result
// (submission) exists to show. A greyed-out card without a result is inert:
// clicking it does nothing.
function isClickable(a) {
  return canSubmit(a) || a.submission_count > 0
}
// Card click: the submission view while (further) submissions are possible,
// otherwise the result view. Only the explicit "Results" button shows the
// result while the card still opens a submission.
function openAnalysis(a) {
  if (canSubmit(a)) {
    router.push(`/analysis/${a.id}`)
  } else if (a.submission_count > 0) {
    openResults(a)
  }
}
function openResults(a) {
  router.push(`/analysis/${a.id}/results`)
}
function actionLabel(a) {
  return canSubmit(a) ? 'Open Analysis' : a.submission_count > 0 ? 'View Result' : 'Open Analysis'
}

async function load() {
  loading.value = true
  try {
    // The summary request is non-critical: if it fails, the card grid still
    // renders (the pass-status bar just stays hidden).
    const [list, sum] = await Promise.all([
      api.get('/analyses'),
      api.get('/me/summary').catch(() => null),
    ])
    analyses.value = list
    summary.value = sum
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

.fc-user__labspace {
  font-size: var(--fc-fs-xs);
  color: var(--fc-text-soft);
}

@media (min-width: 900px) {
  .fc-user__name {
    max-width: none;
  }
}

/* Course result bar: total points, passing line and the pass status tag.
   Now lives in the page footer, below the progress bar. */
.course-summary {
  display: flex;
  align-items: center;
  gap: var(--fc-space-md);
  background: var(--fc-surface);
  border: 1px solid var(--fc-border);
  border-radius: var(--fc-radius, 12px);
  box-shadow: var(--fc-shadow);
  padding: var(--fc-space-sm) var(--fc-space-md);
  flex-wrap: wrap;
}

.course-summary__stat {
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.course-summary__value {
  font-size: var(--fc-fs-lg, 20px);
  font-weight: 800;
  line-height: 1;
}

.course-summary__label {
  font-size: var(--fc-fs-xs);
  color: var(--fc-text-soft);
  white-space: nowrap;
}

.course-summary__divider {
  width: 1px;
  height: 24px;
  background: var(--fc-border);
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

/* Action row: the main submit/result button plus (while further submissions
   are possible) an explicit "Results" button. */
.analysis-card__actions {
  display: flex;
  align-items: center;
  gap: var(--fc-space-xs);
  margin-top: var(--fc-space-xs);
}
.analysis-card__action {
  flex: 1 1 auto;
}

/* Inactive (not yet open / closed) analyses: greyed out and inert. They only
   appear without a result, so clicking them does nothing. */
.fc-card--inactive {
  cursor: default;
  opacity: 0.62;
  filter: grayscale(0.55);
  box-shadow: var(--fc-shadow-sm);
  outline: none;
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

/* --- Course progress footer (in-flow at the bottom of the page) ----------
   The bar's background is a full-width red -> yellow -> green gradient; the
   grey "rest" overlay covers everything right of the current progress, so the
   visible part always sits at the correct position on the 0..max scale. */
/* The footer stacks two rows: the progress bar (with the total/max on the
   right) on top, and the course-points summary bar below it. On large screens
   the page is a min-height:100dvh flex column (see .fc-page rule below) so the
   footer is pushed to the viewport bottom when the content is short. */
.progress-dock {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: var(--fc-space-sm);
  margin-top: auto;
  padding: 14px 0 calc(14px + env(safe-area-inset-bottom, 0px));
  border-top: 1px solid var(--fc-border);
}

/* On large screens, pin the footer to the bottom of the viewport. The page
   becomes a min-height:100dvh flex column; the content area grows to absorb the
   spare space, and the footer (flex-grow:0) stays at the very bottom. Falls back
   gracefully (in-flow) if 100dvh is unsupported. */
@media (min-width: 900px) {
  .fc-page {
    display: flex;
    flex-direction: column;
    min-height: 60vh;
    min-height: 100dvh;
    box-sizing: border-box;
    /* The footer's own padding provides the bottom breathing room, so drop the
       page's bottom padding to let the footer flush to the viewport bottom. */
    padding-bottom: 0;
  }

  .progress-dock {
    flex: 0 0 auto;
  }
}

/* Top row of the footer: the progress bar (fills) with the total/max points
   on the right. */
.progress-dock__row {
  display: flex;
  align-items: center;
  gap: var(--fc-space-md);
  width: 100%;
}

.progress-dock__bar {
  position: relative;
  flex: 1 1 auto;
  height: 10px;
  border-radius: 999px;
  background: linear-gradient(90deg, #ef4444 0%, #f59e0b 55%, #22c55e 100%);
}

.progress-dock__rest {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  background: rgb(228, 231, 237);
  border-radius: 999px;
  transition: width 0.6s cubic-bezier(0.22, 1, 0.36, 1);
}

/* Tick marking the passing line on the 0..max scale. */
.progress-dock__marker {
  position: absolute;
  top: -2px;
  bottom: -2px;
  width: 3px;
  transform: translateX(-1.5px);
  border-radius: 2px;
  background: #ffffff;
  box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.35);
}

.progress-dock__points {
  flex: 0 0 auto;
  font-size: var(--fc-fs-md);
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  color: #dc2626;
  transition: color 0.4s ease;
}

.progress-dock__points--passed {
  color: #16a34a;
}

@media (max-width: 720px) {
  .progress-dock {
    gap: var(--fc-space-sm);
    /* Keep the footer directly below the content on mobile (don't pin to the
       bottom of a long scroll page). */
    margin-top: calc(var(--fc-space-md) + 6px);
    padding: 12px 0 calc(12px + env(safe-area-inset-bottom, 0px));
  }

  .progress-dock__bar {
    height: 8px;
  }

  .progress-dock__points {
    font-size: var(--fc-fs-sm);
  }
}
</style>
