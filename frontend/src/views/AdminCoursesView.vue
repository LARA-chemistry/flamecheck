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

    <!-- Window calendar (week / month views) for the course's analyses -->
    <n-modal v-model:show="calendar.show" preset="card" :title="`Window calendar — ${calendar.courseName}`" style="width: 96vw; max-width: 1040px">
      <n-space vertical size="medium">
        <div class="cal-toolbar">
          <n-radio-group v-model:value="calendar.view" size="small">
            <n-space :wrap="false">
              <n-radio-button value="week">Week</n-radio-button>
              <n-radio-button value="month">Month</n-radio-button>
            </n-space>
          </n-radio-group>
          <span class="cal-toolbar__spacer" />
          <n-text depth="3" class="cal-legend-text" style="font-size: 12px">
            <span class="cal-legend"><i class="cal-legend__swatch cal-legend__swatch--weekend"></i>weekend</span>
            <span class="cal-legend"><i class="cal-legend__dot cal-legend__dot--open"></i>open</span>
            <span class="cal-legend"><i class="cal-legend__dot cal-legend__dot--early"></i>too early</span>
            <span class="cal-legend"><i class="cal-legend__dot cal-legend__dot--late"></i>too late</span>
          </n-text>
        </div>

        <n-spin :show="calendar.loading">
          <n-empty v-if="!calendar.loading && calendarInstances.length === 0" description="No analyses (windows) for this course yet." size="small" />

          <!-- WEEK VIEW: one row per analysis, a bar across the days it spans -->
          <div v-else-if="calendar.view === 'week'" class="weekcal">
            <div class="weekcal__head">
              <div class="weekcal__corner">Analysis</div>
              <div class="weekcal__head-days">
                <div
                  v-for="d in calendarDays"
                  :key="d.dateKey"
                  class="weekcal__day"
                  :class="{ 'weekcal__day--weekend': d.isWeekend }"
                  :style="{ left: d.leftPct + '%', width: d.widthPct + '%' }"
                >
                  <span class="weekcal__day-dow">{{ d.dowLabel }}</span>
                  <span class="weekcal__day-date">{{ d.dayNum }}</span>
                </div>
              </div>
            </div>

            <div class="weekcal__body">
              <div class="weekcal__grid-layer" aria-hidden="true">
                <div
                  v-for="d in calendarWeekendDays"
                  :key="'wk-' + d.dateKey"
                  class="weekcal__weekend"
                  :style="{ left: d.leftPct + '%', width: d.widthPct + '%' }"
                ></div>
                <div
                  v-for="d in calendarDays"
                  :key="'ln-' + d.dateKey"
                  class="weekcal__vline"
                  :class="{ 'weekcal__vline--week': d.isSunday }"
                  :style="{ left: d.leftPct + '%' }"
                ></div>
              </div>

              <div v-for="inst in calendarInstances" :key="inst.id" class="weekcal__row">
                <div class="weekcal__row-label" :title="inst.type">
                  <span class="weekcal__num">#{{ inst.number }}</span>
                  <span class="weekcal__type">{{ inst.type }}</span>
                </div>
                <div class="weekcal__track">
                  <div
                    class="weekcal__bar"
                    :class="`weekcal__bar--${windowStatus(inst)}`"
                    :style="{ left: barPosition(inst).left + '%', width: barPosition(inst).width + '%' }"
                    :title="`${inst.type} #${inst.number}: ${fmt(inst.window_start)} → ${fmt(inst.window_end)}`"
                  >
                    <span class="weekcal__bar-text">{{ fmtShort(inst.window_start) }} – {{ fmtShort(inst.window_end) }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- MONTH VIEW: a Sun..Sat week grid; each day cell lists the analyses
               whose window covers that day -->
          <div v-else class="monthcal">
            <div class="monthcal__dow">
              <span v-for="d in DOW" :key="d" class="monthcal__dow-cell" :class="{ 'monthcal__dow-cell--weekend': d === 'Sun' || d === 'Sat' }">{{ d }}</span>
            </div>
            <div v-for="(week, wi) in calendarMonthWeeks" :key="wi" class="monthcal__week">
              <div
                v-for="cell in week"
                :key="cell.dateKey"
                class="monthcal__cell"
                :class="{
                  'monthcal__cell--weekend': cell.isWeekend,
                  'monthcal__cell--other': !cell.inRange,
                }"
              >
                <span class="monthcal__cell-date" :title="cell.monthLabel + ' ' + cell.dayNum">{{ cell.dayNum }}</span>
                <div class="monthcal__chips">
                  <div
                    v-for="inst in cell.instances"
                    :key="inst.id"
                    class="monthcal__chip"
                    :class="`monthcal__chip--${inst.status}`"
                    :title="`${inst.type} #${inst.number}: ${fmt(inst.start)} → ${fmt(inst.end)}`"
                  >
                    <span class="monthcal__chip-num">#{{ inst.number }}</span>
                    <span class="monthcal__chip-type">{{ inst.type }}</span>
                  </div>
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
  NModal, NSwitch, NTag, NEmpty, NAlert, NRadioGroup, NRadioButton,
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

// Per-course window calendar. view is 'week' (Gantt timeline) or 'month'
// (a classic month grid with one chip per analysis/day it covers).
const calendar = ref({
  show: false,
  loading: false,
  courseId: null,
  courseName: '',
  instances: [],
  view: 'week',
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

// ---- window calendar (week view) ---------------------------------------------
// Sort the course's analyses by their window start so the rows read in
// chronological order.
const calendarInstances = computed(() =>
  [...calendar.value.instances].sort(
    (a, b) => new Date(a.window_start) - new Date(b.window_start),
  ),
)

const DOW = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const DAY_MS = 24 * 60 * 60 * 1000

// Start of a given day (local 00:00:00).
function startOfDay(d) {
  const x = new Date(d)
  x.setHours(0, 0, 0, 0)
  return x
}

// The week-view time axis: whole days from the earliest window's day to the
// latest window's day (inclusive), so every day is a full column.
const calendarRange = computed(() => {
  const list = calendarInstances.value
  if (list.length === 0) return null
  const starts = list.map((i) => startOfDay(new Date(i.window_start)).getTime())
  const ends = list.map((i) => startOfDay(new Date(i.window_end)).getTime())
  const min = Math.min(...starts)
  const max = Math.max(...ends)
  const minEnd = max + DAY_MS // exclusive end (start of the day after the last)
  return { min, max, end: minEnd, span: Math.max(minEnd - min, 1) }
})

// One entry per day in the range: its position/width (%), day-of-week label,
// whether it is a weekend day, and whether it is a Sunday (week boundary).
const calendarDays = computed(() => {
  const r = calendarRange.value
  if (!r) return []
  const days = []
  for (let t = r.min; t <= r.max; t += DAY_MS) {
    const d = new Date(t)
    const dow = d.getDay() // 0 = Sunday … 6 = Saturday
    days.push({
      dateKey: `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`,
      dow,
      dowLabel: DOW[dow],
      dayNum: d.getDate(),
      isWeekend: dow === 0 || dow === 6,
      isSunday: dow === 0,
      leftPct: ((t - r.min) / r.span) * 100,
      widthPct: (DAY_MS / r.span) * 100,
    })
  }
  return days
})

// Weekend days only (for the full-height column tints).
const calendarWeekendDays = computed(() => calendarDays.value.filter((d) => d.isWeekend))

// ---- month view ------------------------------------------------------------
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

// The month-view grid spans whole weeks: from the start of the week that
// contains the earliest window day to the end of the week that contains the
// latest window day. This yields a clean Sun..Sat grid of week-rows.
const calendarMonthWeeks = computed(() => {
  const list = calendarInstances.value
  if (list.length === 0) return []
  const starts = list.map((i) => startOfDay(new Date(i.window_start)).getTime())
  const ends = list.map((i) => startOfDay(new Date(i.window_end)).getTime())
  const minDay = Math.min(...starts)
  const maxDay = Math.max(...ends)
  // Align to the surrounding weeks (Sunday-start).
  const firstWeekStart = minDay - (new Date(minDay).getDay() * DAY_MS)
  const lastDay = maxDay + DAY_MS // start of the day after the last window day
  let lastWeekEnd = lastDay + ((6 - new Date(lastDay - DAY_MS).getDay()) * DAY_MS)
  // Build week rows (each a Sun..Sat run of 7 days).
  const weeks = []
  for (let t = firstWeekStart; t < lastWeekEnd; t += 7 * DAY_MS) {
    const row = []
    for (let k = 0; k < 7; k++) {
      const dayStart = t + k * DAY_MS
      const dayEnd = dayStart + DAY_MS
      const d = new Date(dayStart)
      const dow = d.getDay()
      // Analyses whose window overlaps this day (window_start < dayEnd AND
      // window_end > dayStart).
      const covering = list.filter((i) => {
        const ws = new Date(i.window_start).getTime()
        const we = new Date(i.window_end).getTime()
        return ws < dayEnd && we > dayStart
      })
      row.push({
        dateKey: `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`,
        dayNum: d.getDate(),
        monthLabel: MONTHS[d.getMonth()],
        inRange: dayStart >= minDay && dayStart <= maxDay,
        isWeekend: dow === 0 || dow === 6,
        isSunday: dow === 0,
        instances: covering.map((i) => ({
          id: i.id,
          number: i.number,
          type: i.type,
          status: windowStatus(i),
          start: i.window_start,
          end: i.window_end,
        })),
      })
    }
    weeks.push(row)
  }
  return weeks
})

// Month labels shown above the grid (the distinct months that appear in it).
const calendarMonthLabels = computed(() => {
  const seen = []
  for (const week of calendarMonthWeeks.value) {
    for (const cell of week) {
      if (cell.inRange && !seen.includes(cell.monthLabel)) seen.push(cell.monthLabel)
    }
  }
  return seen
})

// Map an instance's window to its bar's left/width (%) on the day-based axis.
function barPosition(inst) {
  const r = calendarRange.value
  if (!r) return { left: 0, width: 0 }
  const start = new Date(inst.window_start).getTime()
  const end = new Date(inst.window_end).getTime()
  const left = ((start - r.min) / r.span) * 100
  const width = ((end - start) / r.span) * 100
  return { left: Math.max(0, left), width: Math.max(0.5, Math.min(100 - left, width)) }
}

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

/* ---- window calendar (week view) -------------------------------------- */
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
.cal-legend__swatch {
  display: inline-block;
  width: 12px;
  height: 10px;
  border-radius: 2px;
}
.cal-legend__swatch--weekend { background: var(--wk-weekend, #eef2fb); border: 1px solid var(--fc-border); }
.cal-legend__dot--open { background: #18a058; }
.cal-legend__dot--early { background: #f0a020; }
.cal-legend__dot--late { background: #d03050; }

.weekcal {
  font-size: 12px;
  --wk-label-w: 168px;
  --wk-weekend: #eef2fb;       /* weekend column tint */
  --wk-weekend-ink: #5b6b8c;   /* weekend header text */
  --wk-line: var(--fc-border); /* day boundary */
  --wk-week-line: #b7c0d8;     /* thicker week boundary (after Sundays) */
}

/* column header */
.weekcal__head {
  display: flex;
  align-items: stretch;
  border-bottom: 2px solid var(--wk-week-line);
}
.weekcal__corner {
  width: var(--wk-label-w);
  flex: 0 0 var(--wk-label-w);
  display: flex;
  align-items: center;
  padding: 6px 10px;
  font-weight: 700;
  color: var(--fc-text-soft);
  border-right: 1px solid var(--fc-border);
}
.weekcal__head-days {
  position: relative;
  flex: 1;
  height: 40px;
}
.weekcal__day {
  position: absolute;
  top: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1px;
  border-left: 1px solid var(--wk-line);
  overflow: hidden;
}
.weekcal__day--weekend {
  background: var(--wk-weekend);
}
.weekcal__day--weekend .weekcal__day-dow {
  color: var(--wk-weekend-ink);
}
.weekcal__day-dow {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--fc-text-soft);
}
.weekcal__day-date {
  font-size: 12px;
  font-weight: 600;
  color: var(--fc-ink);
}

/* body: shared grid layer + rows */
.weekcal__body {
  position: relative;
}
.weekcal__grid-layer {
  position: absolute;
  inset: 0;
  margin-left: var(--wk-label-w);
  pointer-events: none;
}
.weekcal__weekend {
  position: absolute;
  top: 0;
  bottom: 0;
  background: var(--wk-weekend);
}
.weekcal__vline {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 1px;
  background: var(--wk-line);
}
.weekcal__vline--week {
  width: 2px;
  background: var(--wk-week-line);
}

.weekcal__row {
  position: relative;
  display: flex;
  align-items: stretch;
  height: 34px;
  border-bottom: 1px solid var(--fc-border);
}
.weekcal__row:last-child {
  border-bottom: none;
}
.weekcal__row-label {
  width: var(--wk-label-w);
  flex: 0 0 var(--wk-label-w);
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 10px;
  border-right: 1px solid var(--fc-border);
  overflow: hidden;
  background: var(--fc-surface);
  z-index: 1;
}
.weekcal__num {
  font-weight: 700;
  color: var(--fc-flame-2, #ff8a00);
}
.weekcal__type {
  font-size: 12px;
  color: var(--fc-text-soft);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.weekcal__track {
  position: relative;
  flex: 1;
  z-index: 0;
}
.weekcal__bar {
  position: absolute;
  top: 7px;
  height: 20px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  padding: 0 6px;
  box-sizing: border-box;
  overflow: hidden;
  white-space: nowrap;
  box-shadow: var(--fc-shadow-sm);
}
.weekcal__bar--open { background: rgba(24, 160, 88, 0.9); color: #fff; }
.weekcal__bar--too_early { background: rgba(240, 160, 32, 0.9); color: #fff; }
.weekcal__bar--too_late { background: rgba(208, 48, 80, 0.9); color: #fff; }
.weekcal__bar-text {
  font-size: 11px;
  font-weight: 600;
  text-overflow: ellipsis;
  overflow: hidden;
}

/* toolbar (view toggle + legend) */
.cal-toolbar {
  display: flex;
  align-items: center;
  gap: var(--fc-space-sm);
  flex-wrap: wrap;
}
.cal-toolbar__spacer {
  flex: 1;
}
.cal-legend-text {
  display: inline-flex;
  align-items: center;
}

/* ---- month view ----------------------------------------------------------- */
.monthcal {
  --mc-weekend: var(--wk-weekend, #eef2fb);
  border: 1px solid var(--fc-border);
  border-radius: var(--fc-radius-sm);
  overflow: hidden;
  font-size: 12px;
}
.monthcal__dow {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  background: var(--fc-surface);
  border-bottom: 2px solid var(--fc-border);
}
.monthcal__dow-cell {
  padding: 6px 4px;
  text-align: center;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--fc-text-soft);
  border-left: 1px solid var(--fc-border);
}
.monthcal__dow-cell:first-child {
  border-left: none;
}
.monthcal__dow-cell--weekend {
  color: var(--wk-weekend-ink, #5b6b8c);
}
.monthcal__week {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
}
.monthcal__week + .monthcal__week {
  border-top: 1px solid var(--fc-border);
}
.monthcal__cell {
  min-height: 74px;
  padding: 4px;
  border-left: 1px solid var(--fc-border);
  display: flex;
  flex-direction: column;
  gap: 3px;
  background: var(--fc-surface);
}
.monthcal__cell:first-child {
  border-left: none;
}
.monthcal__cell--weekend {
  background: var(--mc-weekend);
}
.monthcal__cell--other {
  background: transparent;
  opacity: 0.45;
}
.monthcal__cell-date {
  font-size: 11px;
  font-weight: 700;
  color: var(--fc-ink);
  align-self: flex-start;
}
.monthcal__cell--weekend .monthcal__cell-date {
  color: var(--wk-weekend-ink, #5b6b8c);
}
.monthcal__chips {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.monthcal__chip {
  display: flex;
  align-items: center;
  gap: 3px;
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
  color: #fff;
  overflow: hidden;
  white-space: nowrap;
  box-shadow: var(--fc-shadow-sm);
  cursor: default;
}
.monthcal__chip-num {
  flex-shrink: 0;
}
.monthcal__chip-type {
  overflow: hidden;
  text-overflow: ellipsis;
}
.monthcal__chip--open { background: rgba(24, 160, 88, 0.9); }
.monthcal__chip--too_early { background: rgba(240, 160, 32, 0.9); }
.monthcal__chip--too_late { background: rgba(208, 48, 80, 0.9); }
</style>
