<template>
  <n-space vertical size="large">
    <n-card size="small" :bordered="false">
      <div class="page-head">
        <h2 class="page-title">Courses</h2>
        <n-button type="primary" size="small" @click="openCreate">+ New Course</n-button>
      </div>

      <n-data-table :columns="courseCols" :data="courses" size="small" :loading="loading" />
    </n-card>

    <!-- Students in the selected course -->
    <n-card v-if="selected" size="small" :bordered="false">
      <div class="page-head">
        <h2 class="page-title">Students — {{ selected.name }}</h2>
        <n-button size="small" @click="loadStudents(selected.id)">Refresh</n-button>
      </div>
      <n-space vertical size="small">
        <n-empty v-if="!loadingStudents && courseStudents.length === 0" description="No students in this course yet." size="small" />
        <div v-for="s in courseStudents" :key="s.id" class="student-row">
          <span class="student-row__name">{{ s.name || s.username }}</span>
          <n-tag size="small" :bordered="false" type="info">{{ s.username }}</n-tag>
          <span class="student-row__spacer" />
          <n-button size="tiny" tertiary type="error" @click="detachStudent(s)">Remove</n-button>
        </div>
      </n-space>
    </n-card>

    <!-- Create / edit modal -->
    <n-modal v-model:show="modal.show" preset="card" :title="modal.editing ? 'Edit Course' : 'New Course'" style="width: 460px; max-width: 92vw">
      <n-form label-placement="left" label-width="90">
        <n-form-item label="Name">
          <n-input v-model:value="modal.form.name" placeholder="e.g. Inorganic Chemistry WS 2026" />
        </n-form-item>
        <n-form-item label="Semester">
          <n-input v-model:value="modal.form.semester" placeholder="e.g. WS 2026" />
        </n-form-item>
        <n-form-item label="Track">
          <n-input v-model:value="modal.form.track" placeholder="e.g. biology" />
        </n-form-item>
        <n-form-item label="Active">
          <n-switch v-model:value="modal.form.is_active" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button v-if="modal.editing" type="error" ghost @click="removeCourse">Delete</n-button>
          <n-button @click="modal.show = false">Cancel</n-button>
          <n-button type="primary" :loading="modal.saving" @click="saveCourse">Save</n-button>
        </n-space>
      </template>
    </n-modal>

    <n-alert v-if="message" :type="msgType">{{ message }}</n-alert>
  </n-space>
</template>

<script setup>
import { ref, computed, onMounted, h } from 'vue'
import { api } from '../api/client'
import {
  NSpace, NButton, NInput, NDataTable, NCard, NForm, NFormItem, NModal,
  NSwitch, NTag, NEmpty, NAlert,
} from 'naive-ui'

const message = ref('')
const msgType = ref('success')
const loading = ref(true)
const courses = ref([])
const selected = ref(null)

const students = ref([])
const loadingStudents = ref(false)

const modal = ref({
  show: false,
  editing: false,
  saving: false,
  form: { id: null, name: '', semester: '', track: '', is_active: true },
})

const courseStudents = computed(() =>
  students.value.filter((s) => s.course_id === selected.value?.id),
)

const courseCols = [
  {
    title: 'Name',
    key: 'name',
    render: (row) => h('span', { style: 'font-weight:600' }, row.name),
  },
  { title: 'Semester', key: 'semester' },
  { title: 'Track', key: 'track' },
  { title: 'Active', key: 'is_active', render: (row) => (row.is_active ? '✓' : '—') },
  {
    title: 'Actions',
    key: 'actions',
    render: (row) =>
      h('div', { style: 'display:flex;gap:6px' }, [
        h(NButton, { size: 'tiny', type: 'primary', secondary: true, onClick: () => openEdit(row) }, () => 'Edit'),
        h(NButton, { size: 'tiny', secondary: true, onClick: () => selectCourse(row) }, () => 'Students'),
      ]),
  },
]

function selectCourse(row) {
  selected.value = row
  loadStudents()
}

async function loadCourses() {
  loading.value = true
  try {
    courses.value = await api.get('/admin/courses')
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  } finally {
    loading.value = false
  }
}

async function loadStudents() {
  loadingStudents.value = true
  try {
    students.value = await api.get('/admin/students')
  } catch (e) {
    /* ignore */
  } finally {
    loadingStudents.value = false
  }
}

function openCreate() {
  modal.value = { show: true, editing: false, saving: false, form: { id: null, name: '', semester: '', track: '', is_active: true } }
}

function openEdit(row) {
  modal.value = {
    show: true,
    editing: true,
    saving: false,
    form: { id: row.id, name: row.name, semester: row.semester || '', track: row.track || '', is_active: row.is_active },
  }
}

async function saveCourse() {
  const f = modal.value.form
  if (!f.name) {
    message.value = 'Name is required.'
    msgType.value = 'error'
    return
  }
  modal.value.saving = true
  try {
    if (modal.value.editing) {
      await api.put(`/admin/courses/${f.id}`, f)
      message.value = 'Course updated.'
    } else {
      await api.post('/admin/courses', f)
      message.value = 'Course created.'
    }
    modal.value.show = false
    msgType.value = 'success'
    await loadCourses()
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  } finally {
    modal.value.saving = false
  }
}

async function removeCourse() {
  const f = modal.value.form
  if (!confirm(`Delete course "${f.name}"?`)) return
  try {
    await api.delete(`/admin/courses/${f.id}`)
    message.value = 'Course deleted.'
    msgType.value = 'success'
    modal.value.show = false
    if (selected.value?.id === f.id) selected.value = null
    await loadCourses()
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  }
}

async function detachStudent(s) {
  try {
    await api.put(`/admin/students/${s.id}/course`, { student_id: s.id, course_id: null })
    message.value = `${s.username} removed from course.`
    msgType.value = 'success'
    await loadStudents()
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  }
}

onMounted(() => {
  loadCourses()
  loadStudents()
})
</script>

<style scoped>
.page-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--fc-space-sm);
}
.page-title {
  font-size: var(--fc-fs-md);
  font-weight: 700;
  color: var(--fc-ink);
}
.student-row {
  display: flex;
  align-items: center;
  gap: var(--fc-space-xs);
  padding: var(--fc-space-xs) var(--fc-space-sm);
  border: 1px solid var(--fc-border);
  border-radius: var(--fc-radius-sm);
  background: var(--fc-surface);
}
.student-row__name {
  font-weight: 600;
}
.student-row__spacer {
  flex: 1;
}
</style>
