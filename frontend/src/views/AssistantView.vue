<template>
  <div class="page">
    <header class="header">
      <h1>Assistant Dashboard</h1>
      <n-space>
        <n-button size="small" quaternary @click="router.push('/')">Home</n-button>
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
              <n-button size="small" @click="downloadCsv(c.id)">Download CSV</n-button>
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
import { api } from '../api/client'
import {
  NCard, NSpin, NEmpty, NCollapse, NCollapseItem, NSpace, NButton,
  NDataTable, NStatistic,
} from 'naive-ui'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(true)
const courses = ref([])

const cols = [
  { title: 'Student', key: 'name' },
  { title: 'Barcode', key: 'barcode' },
  {
    title: 'Analyses',
    key: 'analyses',
    render: (row) => `${row.analyses.filter((a) => a.window_status === 'submitted').length}/${row.analyses.length}`,
  },
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
</style>
