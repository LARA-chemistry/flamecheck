<template>
  <div class="page">
    <header class="header">
      <h1>Assistant Dashboard</h1>
      <n-space>
        <n-button size="small" quaternary @click="router.push({ name: homeForRole(auth.role) })">Home</n-button>
        <n-button size="small" quaternary @click="handleLogout">Logout</n-button>
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
              <n-data-table :columns="cols" :data="c.students" size="small" :max-height="400" />
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
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { homeForRole } from '../router'
import { api } from '../api/client'
import {
  NCard, NSpin, NEmpty, NCollapse, NCollapseItem, NSpace, NButton,
  NDataTable, NStatistic, NInputNumber,
} from 'naive-ui'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(true)
const courses = ref([])
const overview = ref({})
const overviewLoading = ref({})

const cols = [
  { title: 'Student', key: 'name' },
  { title: 'Barcode', key: 'barcode' },
  {
    title: 'Analyses',
    key: 'analyses',
    render: (row) => `${row.analyses.filter((a) => a.window_status === 'submitted').length}/${row.analyses.length}`,
  },
]

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
.page {
  max-width: 1100px;
  margin: 0 auto;
  padding: 24px;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}
.muted {
  font-size: 13px;
  color: #888;
}
</style>
