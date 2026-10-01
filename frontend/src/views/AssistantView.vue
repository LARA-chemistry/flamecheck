<template>
  <div class="fc-page">
    <header class="fc-header">
      <h1 class="fc-title">Assistant Dashboard</h1>
      <n-space align="center">
        <HelpToggle :active="helpOpen" @click="helpOpen = !helpOpen" />
        <n-button size="small" secondary @click="router.push({ name: homeForRole(auth.role) })">Home</n-button>
        <n-button size="small" secondary @click="handleLogout">Logout</n-button>
      </n-space>
    </header>

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
              <n-data-table :columns="cols" :data="c.students" size="small" :max-height="400" :row-props="rowProps" />
              <n-space align="center">
                <n-button size="small" @click="downloadCsv(c.id)">Download CSV</n-button>
                <n-button
                  size="small"
                  :loading="overviewLoading[c.id]"
                  @click="toggleOverview(c)"
                >
                  {{ overview[c.id] ? 'Hide Substance Overview' : 'Substance Overview' }}
                </n-button>
              </n-space>

              <div v-if="overview[c.id]">
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
      :title="studentModal.student ? `Student: ${studentModal.student.name || studentModal.student.username}` : 'Student'"
      style="width: 860px; max-width: 96vw"
      :segmented="{ content: true }"
    >
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
      <HelpSection title="Export">
        <p>
          "Download CSV" exports the course's results for grading or archiving.
        </p>
      </HelpSection>
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
} from 'naive-ui'
import HelpPanel from '../components/HelpPanel.vue'
import HelpToggle from '../components/HelpToggle.vue'
import HelpSection from '../components/HelpSection.vue'

const helpOpen = ref(false)

const router = useRouter()
const auth = useAuthStore()
const loading = ref(true)
const courses = ref([])
const overview = ref({})
const overviewLoading = ref({})

const studentModal = ref({ show: false, loading: false, student: null, detail: null })

const cols = [
  { title: 'Student', key: 'name' },
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
    render: (row) => row.substances.map((s) => s.name).join(', '),
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
  } finally {
    loading.value = false
  }
}

function downloadCsv(courseId) {
  window.open(`/api/v1/assistant/courses/${courseId}/export/csv`, '_blank')
}

function toggleOverview(course) {
  const key = course.id
  if (overview.value[key]) {
    overview.value[key] = null
    return
  }
  overview.value[key] = { samples: null, data: null }
  loadOverview(course)
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
.analysis-card__correct {
  display: flex;
  align-items: center;
  gap: var(--fc-space-xs);
  margin-bottom: var(--fc-space-sm);
}
</style>
