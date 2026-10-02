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

    <!-- Per-course grading settings -->
    <n-modal v-model:show="grading.show" preset="card" :title="`Grading — ${grading.courseName}`" style="width: 500px; max-width: 94vw">
      <n-text depth="3" style="font-size: 13px; display:block; margin-bottom: 12px">
        Overrides the default grading configuration for this course only.
      </n-text>
      <n-form label-placement="left" label-width="200">
        <n-form-item label="Points per correct ion">
          <n-input-number v-model:value="grading.form.points_per_correct_ion" :min="0" />
        </n-form-item>
        <n-form-item label="Penalty 2nd submission">
          <n-input-number v-model:value="grading.form.penalty_second_submission" :min="0" />
        </n-form-item>
        <n-form-item label="Penalty 3rd submission">
          <n-input-number v-model:value="grading.form.penalty_third_submission" :min="0" />
        </n-form-item>
        <n-form-item label="False positive deduction">
          <n-input-number v-model:value="grading.form.false_positive_deduction" :min="0" />
        </n-form-item>
        <n-form-item label="Grading mode">
          <n-select
            v-model:value="grading.form.grading_mode"
            :options="[{ label: 'Per Ion', value: 'per_ion' }, { label: 'Per Analysis', value: 'per_analysis' }]"
          />
        </n-form-item>
        <n-form-item label="Max submissions per analysis">
          <n-input-number v-model:value="grading.form.max_submissions_per_analysis" :min="1" />
        </n-form-item>
        <n-form-item label="Final score strategy">
          <n-select
            v-model:value="grading.form.final_score_strategy"
            :options="[{ label: 'Best', value: 'best' }, { label: 'Last', value: 'last' }]"
          />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="grading.show = false">Cancel</n-button>
          <n-button type="primary" :loading="grading.saving" @click="saveGrading">Save Course Grading</n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- Assign (enroll) students into the course -->
    <n-modal v-model:show="assign.show" preset="card" :title="`Assign students — ${assign.courseName}`" style="width: 520px; max-width: 94vw">
      <n-space vertical>
        <n-text depth="3" style="font-size: 13px; display:block">
          Students you select are enrolled in this course (their current course, if any, is replaced).
        </n-text>
        <n-select
          v-model:value="assign.studentIds"
          :options="assignableStudentOptions"
          multiple
          filterable
          placeholder="Select students to add to this course"
        />
        <n-text v-if="alreadyInCourseCount" depth="3" style="font-size: 13px">
          {{ alreadyInCourseCount }} student{{ alreadyInCourseCount === 1 ? '' : 's' }} already in this course.
        </n-text>
      </n-space>
      <template #footer>
        <n-space justify="end">
          <n-button @click="assign.show = false">Cancel</n-button>
          <n-button
            type="primary"
            :loading="assign.saving"
            :disabled="assign.studentIds.length === 0"
            @click="saveAssign"
          >
            Assign {{ assign.studentIds.length || '' }} Student{{ assign.studentIds.length === 1 ? '' : 's' }}
          </n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- Window calendar (Gantt) for the course's analyses -->
    <n-modal v-model:show="calendar.show" preset="card" :title="`Window calendar — ${calendar.courseName}`" style="width: 900px; max-width: 96vw">
      <n-space vertical size="medium">
        <n-text depth="3" style="font-size: 13px">
          Each bar is an analysis (announcement) and spans its submission window, plotted on a
          shared time axis. <span class="cal-legend"><i class="cal-legend__dot cal-legend__dot--open"></i>open</span>
          <span class="cal-legend"><i class="cal-legend__dot cal-legend__dot--early"></i>too early</span>
          <span class="cal-legend"><i class="cal-legend__dot cal-legend__dot--late"></i>too late</span>
        </n-text>

        <n-spin :show="calendar.loading">
          <n-empty v-if="!calendar.loading && calendarInstances.length === 0" description="No analyses (windows) for this course yet." size="small" />
          <div v-else class="gantt">
            <!-- time axis -->
            <div class="gantt__axis">
              <div class="gantt__axis-labels">
                <span v-for="t in calendarTicks" :key="t.left" class="gantt__tick" :style="{ left: t.left + '%' }">
                  {{ t.label }}
                </span>
              </div>
            </div>

            <!-- one row per analysis -->
            <div v-for="inst in calendarInstances" :key="inst.id" class="gantt__row">
              <div class="gantt__row-label" :title="inst.type">
                <span class="gantt__num">#{{ inst.number }}</span>
                <span class="gantt__type">{{ inst.type }}</span>
              </div>
              <div class="gantt__track">
                <div class="gantt__grid" aria-hidden="true"></div>
                <div
                  class="gantt__bar"
                  :class="`gantt__bar--${windowStatus(inst)}`"
                  :style="{ left: barPosition(inst).left + '%', width: barPosition(inst).width + '%' }"
                  :title="`${inst.type} #${inst.number}: ${fmt(inst.window_start)} → ${fmt(inst.window_end)}`"
                >
                  <span class="gantt__bar-text">{{ fmtShort(inst.window_start) }} – {{ fmtShort(inst.window_end) }}</span>
                </div>
              </div>
            </div>
          </div>
        </n-spin>
      </n-space>
      <template #footer>
        <n-space justify="end">
          <n-button @click="calendar.show = false">Close</n-button>
        </n-space>
      </template>
    </n-modal>

    <n-alert v-if="message" :type="msgType">{{ message }}</n-alert>
  </n-space>
</template>

<script setup>
import { ref, computed, onMounted, h } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/client'
import {
  NSpace, NButton, NInput, NInputNumber, NSelect, NText, NDataTable, NCard, NForm, NFormItem,
  NModal, NSwitch, NTag, NEmpty, NAlert,
} from 'naive-ui'

const router = useRouter()

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

// Per-course grading settings (overrides the global default for one course).
const grading = ref({
  show: false,
  saving: false,
  courseId: null,
  courseName: '',
  form: {
    points_per_correct_ion: 10,
    penalty_second_submission: 2,
    penalty_third_submission: 4,
    false_positive_deduction: 0,
    grading_mode: 'per_ion',
    max_submissions_per_analysis: 3,
    final_score_strategy: 'best',
  },
})

// Assign (enroll) students into a course.
const assign = ref({
  show: false,
  saving: false,
  courseId: null,
  courseName: '',
  studentIds: [],
})

// Per-course window calendar (a Gantt-style timeline of the analysis windows).
const calendar = ref({
  show: false,
  loading: false,
  courseId: null,
  courseName: '',
  instances: [],
})

const courseStudents = computed(() =>
  students.value.filter((s) => s.course_id === selected.value?.id),
)

// Students that can be enrolled into the course being assigned to. Everyone is
// a candidate (a student can be moved from one course to another); those already
// in the target course are flagged so the admin knows.
const assignableStudentOptions = computed(() =>
  students.value.map((s) => {
    const inTarget = s.course_id === assign.value.courseId
    return {
      label: inTarget ? `${s.name || s.username} (already in course)` : `${s.name || s.username} (${s.course_name ? 'in ' + s.course_name : 'no course'})`,
      value: s.id,
      disabled: inTarget,
    }
  }),
)

const alreadyInCourseCount = computed(
  () => students.value.filter((s) => s.course_id === assign.value.courseId).length,
)

// ---- window calendar (Gantt) -------------------------------------------------
// Sort the course's analyses by their window start so the timeline reads in
// chronological order.
const calendarInstances = computed(() =>
  [...calendar.value.instances].sort(
    (a, b) => new Date(a.window_start) - new Date(b.window_start),
  ),
)

// The shared time axis: from the earliest window start to the latest window end,
// padded a little on each side so bars do not touch the edges.
const calendarRange = computed(() => {
  const list = calendarInstances.value
  if (list.length === 0) return null
  const starts = list.map((i) => new Date(i.window_start).getTime())
  const ends = list.map((i) => new Date(i.window_end).getTime())
  let min = Math.min(...starts)
  let max = Math.max(...ends)
  const pad = Math.max((max - min) * 0.05, 30 * 60 * 1000) // at least 30 min of padding
  return { min: min - pad, max: max + pad, span: Math.max(max - min, 1) }
})

// Map an instance to its bar's left/width (in %) on the shared axis.
function barPosition(inst) {
  const r = calendarRange.value
  if (!r) return { left: 0, width: 0 }
  const start = new Date(inst.window_start).getTime()
  const end = new Date(inst.window_end).getTime()
  const left = ((start - r.min) / r.span) * 100
  const width = ((end - start) / r.span) * 100
  return { left: Math.max(0, left), width: Math.max(0.5, Math.min(100 - left, width)) }
}

// A handful of axis tick labels spread across the range.
const calendarTicks = computed(() => {
  const r = calendarRange.value
  if (!r) return []
  const count = 5
  const ticks = []
  for (let i = 0; i < count; i++) {
    const t = r.min + (r.span * i) / (count - 1)
    const d = new Date(t)
    ticks.push({
      left: (i / (count - 1)) * 100,
      label: `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`,
    })
  }
  return ticks
})

// Window status for coloring (open / too early / too late) relative to now.
function windowStatus(inst) {
  const now = Date.now()
  const start = new Date(inst.window_start).getTime()
  const end = new Date(inst.window_end).getTime()
  if (now < start) return 'too_early'
  if (now > end) return 'too_late'
  return 'open'
}

// Format an ISO datetime for display (local time).
function fmt(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}
// Compact "Mon D HH:mm" form for the bar label.
function fmtShort(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}/${d.getDate()} ${p(d.getHours())}:${p(d.getMinutes())}`
}

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
      h('div', { style: 'display:flex;gap:6px;flex-wrap:wrap' }, [
        h(NButton, { size: 'tiny', type: 'primary', secondary: true, onClick: () => openEdit(row) }, () => 'Edit'),
        h(NButton, { size: 'tiny', secondary: true, onClick: () => openAssign(row) }, () => 'Assign'),
        h(NButton, { size: 'tiny', secondary: true, onClick: () => selectCourse(row) }, () => 'Students'),
        h(NButton, { size: 'tiny', secondary: true, onClick: () => openAnalyses(row) }, () => 'Analyses'),
        h(NButton, { size: 'tiny', secondary: true, onClick: () => openCalendar(row) }, () => 'Calendar'),
        h(NButton, { size: 'tiny', secondary: true, onClick: () => openGrading(row) }, () => 'Grading'),
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

// ---- per-course grading settings ---------------------------------------------
async function openGrading(row) {
  // Mutate fields (rather than reassigning the ref) so the open <n-modal>'s
  // v-model:show binding stays reactive.
  grading.value.show = true
  grading.value.saving = false
  grading.value.courseId = row.id
  grading.value.courseName = row.name
  grading.value.form = {
    points_per_correct_ion: 10,
    penalty_second_submission: 2,
    penalty_third_submission: 4,
    false_positive_deduction: 0,
    grading_mode: 'per_ion',
    max_submissions_per_analysis: 3,
    final_score_strategy: 'best',
  }
  try {
    // The endpoint returns the course's own config or the global default, so the
    // form is always populated with usable starting values.
    grading.value.form = await api.get(`/admin/courses/${row.id}/grading-config`)
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  }
}

async function saveGrading() {
  grading.value.saving = true
  try {
    grading.value.form = await api.put(
      `/admin/courses/${grading.value.courseId}/grading-config`,
      grading.value.form,
    )
    message.value = `Grading saved for ${grading.value.courseName}.`
    msgType.value = 'success'
    grading.value.show = false
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  } finally {
    grading.value.saving = false
  }
}

// ---- assign (enroll) students into a course --------------------------------
function openAssign(row) {
  assign.value = { show: true, saving: false, courseId: row.id, courseName: row.name, studentIds: [] }
  // Make sure we have a fresh student list (with current course assignments).
  loadStudents()
}

async function saveAssign() {
  const a = assign.value
  if (a.studentIds.length === 0) return
  a.saving = true
  let ok = 0
  try {
    for (const sid of a.studentIds) {
      await api.put(`/admin/students/${sid}/course`, { student_id: sid, course_id: a.courseId })
      ok += 1
    }
    message.value = `${ok} student${ok === 1 ? '' : 's'} assigned to ${a.courseName}.`
    msgType.value = 'success'
    a.show = false
    // Refresh the student list; the "Students" panel (if open) re-filters itself.
    await loadStudents()
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  } finally {
    a.saving = false
  }
}

// ---- analyses: open the per-course analysis-assignment workflow ------------
function openAnalyses(row) {
  // Reuse the Assignments page, pre-selecting this course via the query param.
  router.push({ name: 'admin-assignments', query: { course: String(row.id) } })
}

// ---- window calendar: visualise the course's analysis windows -------------
async function openCalendar(row) {
  calendar.value.show = true
  calendar.value.loading = true
  calendar.value.courseId = row.id
  calendar.value.courseName = row.name
  calendar.value.instances = []
  try {
    calendar.value.instances = await api.get(`/admin/analysis-instances?course_id=${row.id}`)
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  } finally {
    calendar.value.loading = false
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

/* ---- window calendar (Gantt) ------------------------------------------ */
.cal-legend {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-left: 10px;
}
.cal-legend__dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
}
.cal-legend__dot--open { background: #18a058; }
.cal-legend__dot--early { background: #f0a020; }
.cal-legend__dot--late { background: #d03050; }

.gantt {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 4px 0;
}
.gantt__axis {
  display: flex;
  align-items: center;
  height: 18px;
}
.gantt__axis-labels {
  position: relative;
  flex: 1;
  margin-left: 180px; /* align with the track (label column width) */
  height: 100%;
}
.gantt__tick {
  position: absolute;
  top: 0;
  transform: translateX(-50%);
  font-size: 11px;
  color: var(--fc-muted);
  white-space: nowrap;
}

.gantt__row {
  display: flex;
  align-items: center;
  gap: 0;
  height: 30px;
}
.gantt__row-label {
  width: 180px;
  flex: 0 0 180px;
  display: flex;
  align-items: center;
  gap: 6px;
  padding-right: 10px;
  border-right: 1px solid var(--fc-border);
  overflow: hidden;
}
.gantt__num {
  font-weight: 700;
  color: var(--fc-flame-2, #ff8a00);
}
.gantt__type {
  font-size: 12px;
  color: var(--fc-text-soft);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.gantt__track {
  position: relative;
  flex: 1;
  height: 100%;
}
/* faint vertical grid lines at the tick positions */
.gantt__grid {
  position: absolute;
  inset: 0;
  background-image: repeating-linear-gradient(
    to right,
    var(--fc-border) 0,
    var(--fc-border) 1px,
    transparent 1px,
    transparent 25%
  );
  opacity: 0.5;
}
.gantt__bar {
  position: absolute;
  top: 5px;
  height: 20px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  padding: 0 6px;
  box-sizing: border-box;
  overflow: hidden;
  white-space: nowrap;
}
.gantt__bar--open { background: rgba(24, 160, 88, 0.85); color: #fff; }
.gantt__bar--too_early { background: rgba(240, 160, 32, 0.85); color: #fff; }
.gantt__bar--too_late { background: rgba(208, 48, 80, 0.85); color: #fff; }
.gantt__bar-text {
  font-size: 11px;
  font-weight: 600;
  text-overflow: ellipsis;
  overflow: hidden;
}
</style>
