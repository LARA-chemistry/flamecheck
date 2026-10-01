<template>
  <n-space vertical size="large">
    <n-card size="small" :bordered="false">
      <div class="page-head">
        <h2 class="page-title">Assign Analyses to Students</h2>
        <n-space align="center">
          <span class="fc-muted">Course</span>
          <n-select
            v-model:value="courseId"
            :options="courseOptions"
            placeholder="Choose a course"
            style="width: 280px"
            @update:value="onCourseChange"
          />
        </n-space>
      </div>

      <n-empty v-if="!courseId" description="Pick a course to manage its assignments." />

      <template v-else>
        <!-- Random substance assignment -->
        <div class="randomize-bar">
          <n-text depth="3" class="hint">
            Randomly assign substances: each student in the chosen announcement gets a random
            subset of the analysis's possible ions as their answer key, plus the matching
            reference substances.
          </n-text>
          <n-space align="center" :wrap="true">
            <n-select
              v-model:value="randomize.number"
              :options="numberOptions"
              placeholder="Announcement #"
              style="width: 150px"
            />
            <n-space align="center" size="small">
              <span class="fc-muted">Ions</span>
              <n-input-number v-model:value="randomize.minIons" :min="1" :max="randomize.maxIons" size="small" style="width: 72px" />
              <span class="fc-muted">–</span>
              <n-input-number v-model:value="randomize.maxIons" :min="randomize.minIons" :max="20" size="small" style="width: 72px" />
            </n-space>
            <n-button type="primary" :loading="randomize.running" :disabled="!randomize.number" @click="runRandomize">
              Randomly assign substances
            </n-button>
          </n-space>
        </div>

        <n-data-table :columns="instanceCols" :data="instances" size="small" :loading="loadingInstances" />
      </template>
    </n-card>

    <!-- Randomize result (per-student preview of what was assigned) -->
    <n-modal v-model:show="randomize.result.show" preset="card" title="Random substance assignment" style="width: 720px; max-width: 94vw">
      <n-space vertical>
        <p class="fc-muted">
          {{ randomize.result.data?.randomized }} students were randomized for announcement #{{ randomize.result.data?.number }}.
          Click "Randomly assign substances" again to re-roll.
        </p>
        <n-data-table :columns="resultCols" :data="randomize.result.data?.students || []" size="small" :max-height="360" />
      </n-space>
      <template #footer>
        <n-space justify="end">
          <n-button @click="randomize.result.show = false">Close</n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- Assign modal for the selected instance -->
    <n-modal v-model:show="assign.show" preset="card" :title="assignTitle" style="width: 520px; max-width: 94vw">
      <n-space vertical>
        <p class="fc-muted">Choose the students who receive this analysis sheet.</p>
        <n-select
          v-model:value="assign.studentIds"
          :options="studentOptions"
          multiple
          filterable
          placeholder="Select students"
        />
        <n-form-item label="Announcement #" label-placement="left" label-width="120">
          <n-input-number v-model:value="assign.number" :min="1" placeholder="e.g. 1" />
        </n-form-item>
      </n-space>
      <template #footer>
        <n-space justify="end">
          <n-button @click="assign.show = false">Cancel</n-button>
          <n-button type="primary" :loading="assign.saving" @click="saveAssignments">Assign</n-button>
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
  NSpace, NButton, NInputNumber, NSelect, NDataTable, NCard, NFormItem,
  NModal, NAlert, NEmpty, NText, NTag,
} from 'naive-ui'

const message = ref('')
const msgType = ref('success')

const courses = ref([])
const courseId = ref(null)
const courseOptions = computed(() => courses.value.map((c) => ({ label: c.name, value: c.id })))

const instances = ref([])
const loadingInstances = ref(false)
const students = ref([])
const assignments = ref([])

const assign = ref({ show: false, saving: false, instanceId: null, number: 1, studentIds: [] })

const randomize = ref({
  number: null,
  minIons: 3,
  maxIons: 5,
  running: false,
  result: { show: false, data: null },
})

const numberOptions = computed(() => {
  const nums = [...new Set(instances.value.map((i) => i.number))].sort((a, b) => a - b)
  return nums.map((n) => ({ label: `#${n}`, value: n }))
})

const resultCols = [
  { title: 'Student', key: 'student' },
  {
    title: 'Answer-key ions',
    key: 'correct_ions',
    render: (row) =>
      h(NSpace, { size: 'small', wrap: true }, row.correct_ions.map((ion) => h(NTag, { size: 'small', bordered: false, type: 'info' }, () => ion.symbol))),
  },
  {
    title: 'Assigned substances',
    key: 'substances',
    render: (row) =>
      row.substances.length
        ? h(NSpace, { size: 'small', wrap: true }, row.substances.map((s) => h(NTag, { size: 'small', bordered: false }, () => s.name)))
        : h(NText, { depth: 3 }, () => 'none'),
  },
]

const studentOptions = computed(() => {
  const inCourse = students.value.filter((s) => s.course_id === courseId.value)
  return inCourse.map((s) => ({ label: `${s.name || s.username} (${s.username})`, value: s.id }))
})

const assignTitle = computed(() => {
  const inst = instances.value.find((i) => i.id === assign.value.instanceId)
  return inst ? `Assign: ${inst.type} (#${inst.number})` : 'Assign'
})

const instanceCols = [
  { title: 'Type', key: 'type' },
  { title: '#', key: 'number', width: 44 },
  {
    title: 'Window',
    key: 'window',
    render: (row) => `${row.window_start.slice(5, 16)} → ${row.window_end.slice(11, 16)}`,
  },
  { title: 'Assigned', key: 'assigned_students', render: (row) => `${row.assigned_students.length}` },
  {
    title: 'Actions',
    key: 'actions',
    render: (row) =>
      h('div', { style: 'display:flex;gap:6px' }, [
        h(NButton, { size: 'tiny', type: 'primary', secondary: true, onClick: () => openAssign(row) }, () => 'Manage'),
      ]),
  },
]

async function loadCourses() {
  try {
    courses.value = await api.get('/admin/courses')
  } catch (e) {
    /* ignore */
  }
}

async function loadStudents() {
  try {
    students.value = await api.get('/admin/students')
  } catch (e) {
    /* ignore */
  }
}

async function loadAssignments() {
  try {
    assignments.value = await api.get(`/admin/assignments?course_id=${courseId.value}`)
  } catch (e) {
    /* ignore */
  }
}

async function loadInstances() {
  if (!courseId.value) {
    instances.value = []
    return
  }
  loadingInstances.value = true
  try {
    instances.value = await api.get(`/admin/analysis-instances?course_id=${courseId.value}`)
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  } finally {
    loadingInstances.value = false
  }
}

function onCourseChange() {
  randomize.value.number = null
  randomize.value.result.show = false
  loadInstances()
  loadAssignments()
}

async function runRandomize() {
  if (!courseId.value || !randomize.value.number) return
  randomize.value.running = true
  try {
    const data = await api.post('/admin/analysis-instances/randomize-substances', {
      course_id: courseId.value,
      number: randomize.value.number,
      min_ions: randomize.value.minIons,
      max_ions: randomize.value.maxIons,
    })
    randomize.value.result.data = data
    randomize.value.result.show = true
    message.value = `Randomized substances for ${data.randomized} students.`
    msgType.value = 'success'
    await loadInstances()
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  } finally {
    randomize.value.running = false
  }
}

function openAssign(row) {
  // Preselect students already assigned to this instance.
  const current = assignments.value
    .filter((a) => a.instance_id === row.id)
    .map((a) => a.student_id)
  assign.value = {
    show: true,
    saving: false,
    instanceId: row.id,
    number: row.number,
    studentIds: current,
  }
}

async function saveAssignments() {
  const a = assign.value
  a.saving = true
  try {
    // Remove existing assignments for this instance, then re-add the selected set.
    const existing = assignments.value.filter((x) => x.instance_id === a.instanceId)
    for (const x of existing) {
      await api.delete(`/admin/assignments/${x.id}`)
    }
    for (const sid of a.studentIds) {
      await api.post('/admin/assignments', {
        instance_id: a.instanceId,
        student_id: sid,
        number: a.number || 1,
      })
    }
    message.value = 'Assignments updated.'
    msgType.value = 'success'
    a.show = false
    await Promise.all([loadAssignments(), loadInstances()])
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  } finally {
    a.saving = false
  }
}

onMounted(async () => {
  await loadCourses()
  await loadStudents()
})
</script>

<style scoped>
.page-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--fc-space-sm);
  margin-bottom: var(--fc-space-sm);
}
.page-title {
  font-size: var(--fc-fs-md);
  font-weight: 700;
  color: var(--fc-ink);
}
.randomize-bar {
  display: flex;
  flex-direction: column;
  gap: var(--fc-space-xs);
  padding: var(--fc-space-sm);
  margin-bottom: var(--fc-space-sm);
  border: 1px solid var(--fc-border, rgba(127, 127, 127, 0.2));
  border-radius: 6px;
}
.hint {
  font-size: var(--fc-fs-sm);
}
</style>
