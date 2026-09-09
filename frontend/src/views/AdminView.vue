<template>
  <div class="page">
    <header class="header">
      <h1>Admin</h1>
      <n-space>
        <n-button size="small" quaternary @click="router.push('/')">Home</n-button>
        <n-button size="small" quaternary @click="handleLogout">Logout</n-button>
      </n-space>
    </header>

    <n-tabs type="card">
      <n-tab-pane name="courses" tab="Courses">
        <n-space vertical>
          <n-space>
            <n-input v-model:value="newCourse.name" placeholder="Name" style="width: 200px" />
            <n-input v-model:value="newCourse.semester" placeholder="Semester" style="width: 120px" />
            <n-input v-model:value="newCourse.track" placeholder="Track" style="width: 120px" />
            <n-button type="primary" @click="addCourse">Add Course</n-button>
          </n-space>
          <n-data-table :columns="courseCols" :data="courses" size="small" />
        </n-space>
      </n-tab-pane>

      <n-tab-pane name="grading" tab="Grading">
        <n-space vertical>
          <n-form label-placement="left" label-width="220">
            <n-form-item label="Points per correct ion">
              <n-input-number v-model:value="grading.points_per_correct_ion" :min="0" />
            </n-form-item>
            <n-form-item label="Penalty 2nd submission">
              <n-input-number v-model:value="grading.penalty_second_submission" :min="0" />
            </n-form-item>
            <n-form-item label="Penalty 3rd submission">
              <n-input-number v-model:value="grading.penalty_third_submission" :min="0" />
            </n-form-item>
            <n-form-item label="False positive deduction">
              <n-input-number v-model:value="grading.false_positive_deduction" :min="0" />
            </n-form-item>
            <n-form-item label="Grading mode">
              <n-select
                v-model:value="grading.grading_mode"
                :options="[{ label: 'Per Ion', value: 'per_ion' }, { label: 'Per Analysis', value: 'per_analysis' }]"
              />
            </n-form-item>
            <n-form-item label="Max submissions per analysis">
              <n-input-number v-model:value="grading.max_submissions_per_analysis" :min="1" />
            </n-form-item>
            <n-form-item label="Final score strategy">
              <n-select
                v-model:value="grading.final_score_strategy"
                :options="[{ label: 'Best', value: 'best' }, { label: 'Last', value: 'last' }]"
              />
            </n-form-item>
            <n-button type="primary" @click="saveGrading">Save</n-button>
          </n-form>
        </n-space>
      </n-tab-pane>

      <n-tab-pane name="types" tab="Analysis Types">
        <n-data-table :columns="typeCols" :data="types" size="small" />
      </n-tab-pane>
    </n-tabs>

    <n-alert v-if="message" :type="msgType" style="margin-top: 12px">{{ message }}</n-alert>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { api } from '../api/client'
import {
  NTabs, NTabPane, NSpace, NButton, NInput, NInputNumber, NSelect, NForm,
  NFormItem, NDataTable, NAlert,
} from 'naive-ui'

const router = useRouter()
const auth = useAuthStore()
const message = ref('')
const msgType = ref('success')

const courses = ref([])
const newCourse = ref({ name: '', semester: '', track: '' })
const types = ref([])
const grading = ref({
  points_per_correct_ion: 10,
  penalty_second_submission: 2,
  penalty_third_submission: 4,
  false_positive_deduction: 0,
  grading_mode: 'per_ion',
  max_submissions_per_analysis: 3,
  final_score_strategy: 'best',
})

const courseCols = [
  { title: 'ID', key: 'id', width: 60 },
  { title: 'Name', key: 'name' },
  { title: 'Semester', key: 'semester' },
  { title: 'Track', key: 'track' },
  { title: 'Active', key: 'is_active' },
]
const typeCols = [
  { title: 'ID', key: 'id', width: 60 },
  { title: 'Name', key: 'name' },
  { title: 'Ions', key: 'ions', render: (row) => `${row.ions.length}` },
]

async function loadCourses() {
  try {
    courses.value = await api.get('/admin/courses')
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  }
}
async function loadTypes() {
  try {
    types.value = await api.get('/admin/analysis-types')
  } catch (e) {
    /* ignore */
  }
}
async function loadGrading() {
  try {
    grading.value = await api.get('/admin/grading-config')
  } catch (e) {
    /* ignore */
  }
}

async function addCourse() {
  if (!newCourse.value.name) return
  try {
    await api.post('/admin/courses', newCourse.value)
    newCourse.value = { name: '', semester: '', track: '' }
    await loadCourses()
    message.value = 'Course added.'
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  }
}

async function saveGrading() {
  try {
    await api.put('/admin/grading-config', grading.value)
    message.value = 'Grading config saved.'
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  }
}

function handleLogout() {
  auth.logout()
  router.push('/login')
}

onMounted(() => {
  loadCourses()
  loadTypes()
  loadGrading()
})
</script>

<style scoped>
.page {
  max-width: 1000px;
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
