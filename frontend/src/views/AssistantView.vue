<template>
  <div class="fc-page">
    <header class="fc-header">
      <h1 class="fc-title">Assistant Dashboard</h1>
      <n-space align="center">
        <n-badge :value="unreadCount" :show-zero="false" :offset="[-4, 4]">
          <n-button size="small" secondary :type="showNotifs ? 'primary' : 'default'" @click="showNotifs = !showNotifs">
            Notifications
          </n-button>
        </n-badge>
        <HelpToggle :active="helpOpen" @click="helpOpen = !helpOpen" />
        <n-button size="small" secondary @click="router.push({ name: homeForRole(auth.role) })">Home</n-button>
        <n-button size="small" secondary @click="handleLogout">Logout</n-button>
      </n-space>
    </header>

    <!-- Re-trial notifications: shown on login so supporting assistants know a
         student was handed a fresh analysis to review / edit. -->
    <n-card v-if="notifications.length" size="small" class="notif-banner" :class="{ 'notif-banner--collapsed': !showNotifs }">
      <template #header>
        <n-space align="center" justify="space-between" style="width: 100%">
          <span class="notif-banner__title">
            New re-trial analyses
            <n-tag v-if="unreadCount" type="warning" size="small" round>{{ unreadCount }} new</n-tag>
          </span>
          <n-button
            v-if="unreadCount"
            size="tiny"
            quaternary
            type="primary"
            :loading="notifsLoading"
            @click="markAllRead"
          >
            Mark all as read
          </n-button>
        </n-space>
      </template>
      <n-spin :show="notifsLoading">
        <n-space vertical size="small">
          <div v-for="n in notifications" :key="n.id" class="notif-item" :class="{ 'notif-item--read': n.read }">
            <span class="notif-item__text">
              <strong>{{ n.student_name }}</strong> — a new {{ n.type }} analysis (no. {{ n.number }}) was generated in
              <em>{{ n.course_name }}</em>.
            </span>
            <n-button
              v-if="!n.read"
              size="tiny"
              secondary
              type="primary"
              @click="markRead(n)"
            >
              Mark as read
            </n-button>
          </div>
        </n-space>
      </n-spin>
    </n-card>

    <n-card title="Courses" size="large">
      <n-spin :show="loading">
        <n-empty v-if="!loading && courses.length === 0" description="No courses assigned." />
        <n-collapse v-else>
          <n-collapse-item v-for="c in courses" :key="c.id" :title="`${c.name} (${c.semester})`">
            <n-space vertical>
              <n-space>
                <n-statistic label="Total" :value="c.stats.total_assignments" />
                <n-statistic label="Submitted" :value="c.stats.submitted" />
                <n-statistic label="Pending" :value="c.stats.pending" />
                <n-statistic label="Avg Score" :value="c.stats.average_score ?? '—'" />
              </n-space>

              <!-- View switcher: Students (roster) vs. Substance (overview),
                   placed above the table. -->
              <n-radio-group
                :value="viewOf(c)"
                size="small"
                @update:value="(v) => switchCourseView(c, v)"
              >
                <n-radio-button value="students">
                  <n-icon :component="StudentsIcon" :size="15" :depth="viewOf(c) === 'students' ? 3 : 0" />
                  Students
                </n-radio-button>
                <n-radio-button value="substance">
                  <n-icon :component="SubstanceIcon" :size="15" :depth="viewOf(c) === 'substance' ? 3 : 0" />
                  Substance
                </n-radio-button>
              </n-radio-group>

              <!-- View content, keyed by course + active view so Vue swaps the
                   whole subtree (avoids mis-patching the v-for list). -->
              <div :key="`${c.id}:${viewOf(c)}`">
                <!-- Students view: the course roster. -->
                <template v-if="viewOf(c) !== 'substance'">
                  <n-data-table
                    :columns="cols"
                    :data="c.students"
                    size="small"
                    :max-height="400"
                    :row-props="rowProps"
                  />
                  <n-space align="center">
                    <n-button size="small" @click="downloadCsv(c.id)">Download CSV</n-button>
                  </n-space>
                </template>

                <!-- Substance view: samples per analysis + overview tables. -->
                <template v-else>
                  <n-space align="center" style="margin-bottom: 8px">
                    <span class="muted">Samples per analysis</span>
                    <n-input-number
                      v-model:value="overview[c.id].samples"
                      size="small"
                      :min="1"
                      :show-button="false"
                      placeholder="one per student (default)"
                      style="width: 180px"
                    />
                    <n-button
                      size="small"
                      type="primary"
                      :loading="overviewLoading[c.id]"
                      @click="loadOverview(c)"
                    >
                      Update
                    </n-button>
                  </n-space>

                  <div v-if="!overview[c.id].data" class="muted">Loading…</div>
                  <template v-else>
                    <n-data-table
                      :columns="overviewAnalysisCols"
                      :data="overview[c.id].data.analyses"
                      size="small"
                    />
                    <p class="muted" style="margin: 12px 0 4px">
                      Substance totals for the whole course
                    </p>
                    <n-data-table
                      :columns="overviewTotalCols"
                      :data="overview[c.id].data.totals"
                      size="small"
                      :max-height="320"
                    />
                    <n-space style="margin-top: 12px">
                      <n-statistic label="Distinct substances" :value="overview[c.id].data.distinct_substances" />
                      <n-statistic label="Total substance units" :value="overview[c.id].data.total_units" />
                    </n-space>
                  </template>
                </template>
              </div>
            </n-space>
          </n-collapse-item>
        </n-collapse>
      </n-spin>
    </n-card>

    <!-- Per-student statistics -->
    <n-modal
      v-model:show="studentModal.show"
      preset="card"
      style="width: 860px; max-width: 96vw"
      :segmented="{ content: true }"
    >
      <template #header>
        <div class="student-modal__title">
          <span class="student-modal__name">{{
            studentModal.student ? studentModal.student.full_name || studentModal.student.username : 'Student'
          }}</span>
          <span v-if="studentModal.student?.full_name" class="muted">({{ studentModal.student.username }})</span>
          <strong v-if="studentModal.student?.labspace_id" class="student-modal__labspace">
            {{ studentModal.student.labspace_id }}
          </strong>
        </div>
      </template>
      <n-spin :show="studentModal.loading">
        <n-empty v-if="!studentModal.loading && !studentModal.detail" description="No data." />
        <n-space v-else vertical size="large">
          <!-- Overall statistics -->
          <n-space size="large" align="center">
            <n-statistic label="Analyses" :value="studentModal.detail ? studentModal.detail.length : 0" />
            <n-statistic label="Submitted" :value="studentModal.detail ? submittedCount : 0" />
            <n-statistic label="Total score" :value="studentModal.detail ? totalScore : '—'" />
            <n-statistic label="Average" :value="studentModal.detail ? avgScore : '—'" />
            <n-statistic label="Best" :value="studentModal.detail ? bestScore : '—'" />
          </n-space>

          <!-- Per-analysis breakdown -->
          <n-space vertical v-for="a in (studentModal.detail || [])" :key="a.analysis_id">
            <n-card size="small" :bordered="false" class="analysis-card">
              <template #header>
                <div class="analysis-card__head">
                  <span class="analysis-card__title">{{ a.analysis }}</span>
                  <n-tag :type="submittedTagType(a)" round size="small">{{ a.submissions.length ? 'Submitted' : 'Pending' }}</n-tag>
                  <span v-if="lastSubmittedAt(a)" class="analysis-card__submitted-at" :title="`Last submitted ${lastSubmittedAt(a)} (UTC)`">
                    {{ lastSubmittedAt(a) }}
                  </span>
                </div>
              </template>
              <template #header-extra>
                <span class="analysis-card__score">
                  Score: <strong>{{ finalScore(a) ?? '—' }}</strong>
                </span>
              </template>

              <div class="analysis-card__correct">
                <span class="muted">Correct ions:</span>
                <n-space size="small" style="flex-wrap: wrap">
                  <n-tag v-for="i in a.correct_ions" :key="i.id" size="small" :bordered="false" type="success">
                    {{ i.symbol }}
                  </n-tag>
                </n-space>
              </div>

              <n-empty v-if="a.submissions.length === 0" description="No submissions yet." size="small" />
              <n-data-table
                v-else
                :columns="submissionCols"
                :data="a.submissions"
                size="small"
                :bordered="false"
              />
            </n-card>
          </n-space>
        </n-space>
      </n-spin>
    </n-modal>

    <HelpPanel v-model:open="helpOpen" title="Assistant help">
      <HelpSection title="Your courses">
        <p>
          Each course you support is listed with live statistics: total
          assignments, submitted, pending and the class average score.
        </p>
      </HelpSection>
      <HelpSection title="Student login">
        <p>
          Students sign in with their username and password, by scanning their
          personal barcode (listed per student below), or - if your course uses
          OAuth - via the external identity provider. New OAuth students first
          pick their course on the registration page.
        </p>
      </HelpSection>
      <HelpSection title="Student statistics">
        <p>
          Click any student row to open their per-analysis breakdown: submitted
          vs. pending, final scores, and the ions they selected against the
          correct set.
        </p>
      </HelpSection>
      <HelpSection title="Substance overview">
        <p>
          "Substance Overview" groups each announcement by sample composition
          (the correct ion set) and lists the salts to prepare, with per-course
          totals. Set "samples per analysis" to scale the preparation counts.
        </p>
      </HelpSection>
      <HelpSection title="Ion symbols">
        <p>
          Ions use one canonical symbol - formula, sign, magnitude with the
          digit always present (e.g. <code>Na+1</code>, <code>Mg+2</code>,
          <code>SO4-2</code>). In the UI they are rendered with the IUPAC
          superscript (magnitude before the sign): SO<sub>4</sub><sup>2&#8722;</sup>,
          Na<sup>+</sup>.
        </p>
      </HelpSection>
      <HelpSection title="Export">
        <p>
          "Download CSV" exports the course's results for grading or archiving.
        </p>
      </HelpSection>
      <AboutSection />
    </HelpPanel>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, h } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { homeForRole } from '../router'
import { api } from '../api/client'
import {
  NCard, NSpin, NEmpty, NCollapse, NCollapseItem, NSpace, NButton,
  NDataTable, NStatistic, NInputNumber, NModal, NTag, NProgress,
  NRadioGroup, NRadioButton, NIcon, NBadge,
} from 'naive-ui'
import HelpPanel from '../components/HelpPanel.vue'
import HelpToggle from '../components/HelpToggle.vue'
import HelpSection from '../components/HelpSection.vue'
import AboutSection from '../components/AboutSection.vue'

const helpOpen = ref(false)

const router = useRouter()
const auth = useAuthStore()
const loading = ref(true)
const courses = ref([])
const overview = ref({})
const overviewLoading = ref({})

// Re-trial notifications (a student was handed a fresh analysis to review).
const notifications = ref([])
const notifsLoading = ref(false)
const showNotifs = ref(false)
const unreadCount = computed(() => notifications.value.filter((n) => !n.read).length)

// Per-course active view: 'students' (default) or 'substance'.
const courseView = ref({})
function viewOf(course) {
  return courseView.value[course.id] || 'students'
}

// Switch a course's view; lazy-init the substance-overview state so the panel
// can render (and trigger its load) the first time the Substance tab is used.
function switchCourseView(course, view) {
  courseView.value[course.id] = view
  if (view === 'substance' && !overview.value[course.id]) {
    overview.value[course.id] = { samples: null, data: null }
    loadOverview(course)
  }
}

// Inline SVG icon components (no icon library in this app).
const StudentsIcon = {
  render: () =>
    h(
      'svg',
      { viewBox: '0 0 24 24', width: '1em', height: '1em', 'aria-hidden': 'true', fill: 'none', stroke: 'currentColor', 'stroke-width': '1.8', 'stroke-linecap': 'round', 'stroke-linejoin': 'round' },
      [
        h('path', { d: 'M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2' }),
        h('circle', { cx: '9', cy: '7', r: '4' }),
        h('path', { d: 'M23 21v-2a4 4 0 0 0-3-3.87' }),
        h('path', { d: 'M16 3.13a4 4 0 0 1 0 7.75' }),
      ],
    ),
}
const SubstanceIcon = {
  render: () =>
    h(
      'svg',
      { viewBox: '0 0 24 24', width: '1em', height: '1em', 'aria-hidden': 'true', fill: 'none', stroke: 'currentColor', 'stroke-width': '1.8', 'stroke-linecap': 'round', 'stroke-linejoin': 'round' },
      [
        h('path', { d: 'M9 3h6' }),
        h('path', { d: 'M10 3v6.34L5.5 17.5A2 2 0 0 0 7.3 20.5h9.4a2 2 0 0 0 1.8-3L14 9.34V3' }),
        h('path', { d: 'M7 14h10' }),
      ],
    ),
}

const studentModal = ref({ show: false, loading: false, student: null, detail: null })

const cols = [
  { title: 'Student', key: 'full_name', render: (row) => row.full_name || row.username },
  { title: 'Barcode', key: 'barcode' },
  {
    title: 'Analyses',
    key: 'analyses',
    render: (row) => `${submittedOf(row)}/${row.analyses.length}`,
  },
  {
    title: 'Progress',
    key: 'progress',
    width: 160,
    render: (row) => renderProgress(row),
  },
  {
    title: 'Avg',
    key: 'avg',
    render: (row) => avgFor(row) ?? '—',
  },
  {
    title: '',
    key: 'actions',
    width: 90,
    render: (row) =>
      h('button', { class: 'link-btn', onClick: () => openStudent(row) }, 'Details'),
  },
]

// Number of analyses the student has submitted (window_status === 'submitted').
function submittedOf(row) {
  return row.analyses.filter((a) => a.window_status === 'submitted').length
}

// A per-student progress bar: how far through their assigned analyses they are.
// Green when complete, orange while in progress, neutral when nothing submitted.
function renderProgress(row) {
  const total = row.analyses.length
  const done = submittedOf(row)
  const pct = total ? Math.round((done / total) * 100) : 0
  const status = total && done >= total ? 'success' : done > 0 ? 'error' : 'default'
  return h(
    NProgress,
    {
      percentage: pct,
      status,
      height: 10,
      showIndicator: true,
      fillBorder: true,
      style: 'min-width: 120px',
    },
    () => h('div', { class: 'progress-label' }, `${done}/${total} · ${pct}%`),
  )
}

// Make the whole roster row clickable to open the student's statistics.
function rowProps(row) {
  return {
    style: 'cursor: pointer',
    onClick: () => openStudent(row),
  }
}

function avgFor(row) {
  const scores = row.analyses.map((a) => a.score).filter((s) => s != null)
  if (!scores.length) return null
  return Math.round((scores.reduce((x, y) => x + y, 0) / scores.length) * 100) / 100
}

// ---- per-student statistics ----------------------------------------------
const submittedCount = computed(() =>
  (studentModal.value.detail || []).filter((a) => a.submissions.length > 0).length,
)
const totalScore = computed(() =>
  (studentModal.value.detail || []).reduce((sum, a) => sum + (finalScore(a) ?? 0), 0),
)
const avgScore = computed(() => {
  const scores = (studentModal.value.detail || [])
    .map((a) => finalScore(a))
    .filter((s) => s != null)
  if (!scores.length) return null
  return Math.round((scores.reduce((x, y) => x + y, 0) / scores.length) * 100) / 100
})
const bestScore = computed(() => {
  const scores = (studentModal.value.detail || [])
    .map((a) => finalScore(a))
    .filter((s) => s != null)
  return scores.length ? Math.max(...scores) : null
})

// The roster already carries each analysis's final `score`; prefer it, else
// fall back to the best submission in the detail payload.
function finalScore(a) {
  const roster = studentModal.value.student?.analyses?.find(
    (r) => r.id === a.analysis_id,
  )
  if (roster && roster.score != null) return roster.score
  if (!a.submissions.length) return null
  return Math.max(...a.submissions.map((s) => s.score))
}

function submittedTagType(a) {
  return a.submissions.length ? 'success' : 'default'
}

// Render a UTC ISO timestamp as an exact "YYYY-MM-DD HH:MM:SS" string.
function fmtSubmittedAt(iso) {
  if (!iso) return ''
  return iso.slice(0, 19).replace('T', ' ')
}

// The exact datetime of the student's most recent submission for this analysis
// (empty while the analysis is still pending). Submissions arrive ordered by
// `submitted_at`, so the last entry is the latest.
function lastSubmittedAt(a) {
  if (!a.submissions.length) return ''
  return fmtSubmittedAt(a.submissions[a.submissions.length - 1].submitted_at)
}

const submissionCols = [
  { title: '#', key: 'submission_number', width: 44 },
  { title: 'Submitted', key: 'submitted_at', render: (row) => row.submitted_at.replace('T', ' ').slice(0, 16) },
  { title: 'Score', key: 'score', width: 60 },
  { title: 'Correct', key: 'correct_count', width: 70 },
  { title: 'Wrong', key: 'wrong_count', width: 70 },
  { title: 'Missing', key: 'missing_count', width: 70 },
  { title: 'Penalty', key: 'penalty', width: 70 },
  {
    title: 'Selected ions',
    key: 'selected_ions',
    render: (row) => row.selected_ions.map((i) => i.symbol).join(', ') || '—',
  },
]

async function openStudent(row) {
  studentModal.value = { show: true, loading: true, student: row, detail: null }
  try {
    studentModal.value.detail = await api.get(`/assistant/students/${row.id}/submissions`)
  } catch (e) {
    studentModal.value.detail = null
    window.alert(e.message || 'Failed to load the student\'s statistics.')
  } finally {
    studentModal.value.loading = false
  }
}

const overviewAnalysisCols = [
  { title: '#', key: 'number', width: 50 },
  { title: 'Analysis', key: 'type' },
  { title: 'Students', key: 'student_count', width: 90 },
  { title: 'Samples', key: 'sample_count', width: 90 },
  {
    title: 'Correct ions',
    key: 'correct_ions',
    render: (row) => row.correct_ions.map((i) => i.symbol).join(', '),
  },
  {
    title: 'Substances used',
    key: 'substances',
    // Each substance name links to its PubChem page when the CID is known.
    render: (row) =>
      row.substances.length
        ? h(NSpace, { size: 'small', wrap: true }, row.substances.map((s, i) =>
            s.pubchem_url
              ? h('a', { key: i, href: s.pubchem_url, target: '_blank', rel: 'noopener noreferrer' }, s.name)
              : h('span', { key: i }, s.name)))
        : '—',
  },
]

const overviewTotalCols = [
  { title: 'Substance', key: 'name' },
  { title: 'Formula', key: 'formula', width: 120 },
  { title: 'Used in analyses', key: 'used_in_analyses', width: 140 },
  { title: 'Total', key: 'count', width: 80 },
]

async function load() {
  loading.value = true
  try {
    courses.value = await api.get('/assistant/courses')
    await loadNotifications()
  } finally {
    loading.value = false
  }
}

async function loadNotifications() {
  notifsLoading.value = true
  try {
    notifications.value = await api.get('/assistant/notifications')
    // Open the panel on login when there is something new to see.
    if (notifications.value.some((n) => !n.read)) showNotifs.value = true
  } catch {
    notifications.value = []
  } finally {
    notifsLoading.value = false
  }
}

async function markRead(n) {
  try {
    await api.post(`/assistant/notifications/${n.id}/read`, {})
    n.read = true
  } catch (e) {
    window.alert(e.message || 'Failed to mark the notification as read.')
  }
}

async function markAllRead() {
  await Promise.all(notifications.value.filter((n) => !n.read).map((n) => markRead(n)))
}

function downloadCsv(courseId) {
  window.open(`/api/v1/assistant/courses/${courseId}/export/csv`, '_blank')
}

async function loadOverview(course) {
  const key = course.id
  const state = overview.value[key]
  if (!state) return
  overviewLoading.value[key] = true
  try {
    const params = state.samples ? `?samples_per_analysis=${state.samples}` : ''
    state.data = await api.get(`/assistant/courses/${key}/substance-overview${params}`)
  } catch (e) {
    state.data = null
    window.alert(e.message || 'Failed to load the substance overview.')
  } finally {
    overviewLoading.value[key] = false
  }
}

function handleLogout() {
  auth.logout()
  router.push('/login')
}

onMounted(load)
</script>

<style scoped>
.muted {
  font-size: var(--fc-fs-sm);
  color: var(--fc-muted);
}
.student-modal__title {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
}
.student-modal__name {
  font-weight: 700;
  color: var(--fc-ink);
}
.student-modal__labspace {
  font-weight: 700;
  color: var(--fc-flame-2);
  font-variant-numeric: tabular-nums;
}
.notif-banner {
  margin-bottom: 16px;
  border-left: 3px solid var(--n-warning-color, #f0a020);
}
.notif-banner--collapsed :deep(.n-card__content) {
  display: none;
}
.notif-banner__title {
  font-weight: 600;
}
.notif-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 8px;
  border-radius: 6px;
  background: color-mix(in srgb, var(--n-warning-color, #f0a020) 8%, transparent);
}
.notif-item--read {
  background: transparent;
  opacity: 0.6;
}
.notif-item__text {
  font-size: var(--fc-fs-sm);
}
.link-btn {
  border: none;
  background: none;
  color: var(--fc-flame-2);
  font-weight: 600;
  font-size: var(--fc-fs-sm);
  cursor: pointer;
  padding: 2px 4px;
}
.link-btn:hover {
  text-decoration: underline;
}
.progress-label {
  margin-top: 2px;
  font-size: var(--fc-fs-xs);
  color: var(--fc-text-soft);
}
.analysis-card__head {
  display: flex;
  align-items: center;
  gap: var(--fc-space-xs);
}
.analysis-card__title {
  font-weight: 700;
  color: var(--fc-ink);
}
.analysis-card__score {
  font-size: var(--fc-fs-sm);
  color: var(--fc-text-soft);
}
.analysis-card__submitted-at {
  font-size: var(--fc-fs-xs);
  color: var(--fc-muted);
  font-variant-numeric: tabular-nums;
}
.analysis-card__correct {
  display: flex;
  align-items: center;
  gap: var(--fc-space-xs);
  margin-bottom: var(--fc-space-sm);
}
</style>
