<template>
  <n-space vertical size="large">
    <n-card size="small" :bordered="false">
      <div class="page-head">
        <h2 class="page-title">Courses</h2>
        <n-button type="primary" size="small" @click="openCreate">+ New Course</n-button>
      </div>

      <!-- Clicking a course row opens the course detail view below (like the
           assistant's course view). -->
      <n-data-table
        :columns="courseCols"
        :data="courses"
        size="small"
        :loading="loading"
        :row-props="courseRowProps"
      />
    </n-card>

    <!-- Course detail view: tabbed navigation over the per-course work areas. -->
    <n-card v-if="selected" size="small" :bordered="false">
      <div class="page-head">
        <h2 class="page-title">
          {{ selected.name }}
          <span class="muted">({{ selected.semester }}{{ selected.track ? ', ' + selected.track : '' }})</span>
        </h2>
        <n-space size="small">
          <n-button size="small" @click="openEdit(selected)">Edit</n-button>
        </n-space>
      </div>

      <n-radio-group
        :value="courseView"
        size="small"
        class="course-nav"
        @update:value="switchCourseView"
      >
        <n-radio-button value="assign">Assign</n-radio-button>
        <n-radio-button value="students">Students</n-radio-button>
        <n-radio-button value="analyses">Analyses</n-radio-button>
        <n-radio-button value="grading">Grading</n-radio-button>
        <n-radio-button value="calendar">Calendar</n-radio-button>
      </n-radio-group>

      <!-- View content, keyed by course + active view so Vue swaps the whole
           subtree (avoids mis-patching the v-for lists). -->
      <div :key="`${selected.id}:${courseView}`">
        <!-- Students: the course roster. -->
        <template v-if="courseView === 'students'">
          <n-space align="center" style="margin-bottom: 8px">
            <n-button type="primary" size="small" @click="openAddStudent">+ Add Student</n-button>
            <n-button size="small" @click="openImport">Import CSV</n-button>
            <n-button size="small" @click="loadStudents()">Refresh</n-button>
          </n-space>
          <n-empty v-if="!loadingStudents && courseStudents.length === 0" description="No students in this course yet." size="small" />
          <n-data-table v-else :columns="studentCols" :data="courseStudents" size="small" :loading="loadingStudents" />
        </template>

        <!-- Assign: enroll (or move) students into this course. -->
        <template v-else-if="courseView === 'assign'">
          <n-space vertical>
            <n-text depth="3" style="font-size: 13px">
              Students you select are enrolled in this course (their current course, if any, is replaced).
            </n-text>
            <n-select
              v-model:value="assignStudentIds"
              :options="assignableStudentOptions"
              multiple
              filterable
              placeholder="Select students to add to this course"
              style="max-width: 560px"
            />
            <n-text v-if="alreadyInCourseCount" depth="3" style="font-size: 13px">
              {{ alreadyInCourseCount }} student{{ alreadyInCourseCount === 1 ? '' : 's' }} already in this course.
            </n-text>
            <n-button
              type="primary"
              size="small"
              :loading="assignSaving"
              :disabled="assignStudentIds.length === 0"
              @click="saveAssign"
            >
              Assign {{ assignStudentIds.length || '' }} Student{{ assignStudentIds.length === 1 ? '' : 's' }}
            </n-button>
          </n-space>
        </template>

        <!-- Analyses: this course's analysis instances. -->
        <template v-else-if="courseView === 'analyses'">
          <n-space align="center" style="margin-bottom: 8px">
            <n-button type="primary" size="small" @click="goToAssignments">Manage Assignments</n-button>
            <n-button size="small" @click="loadCourseInstances()">Refresh</n-button>
          </n-space>
          <n-empty v-if="!loadingInstances && courseInstances.length === 0" description="No analyses for this course yet." size="small" />
          <n-data-table
            v-else
            :columns="analysisCols"
            :data="courseInstances"
            size="small"
            :loading="loadingInstances"
          />
        </template>

        <!-- Grading: per-course grading configuration. -->
        <template v-else-if="courseView === 'grading'">
          <n-space vertical>
            <n-text depth="3" style="font-size: 13px">
              Overrides the default grading configuration for this course only.
            </n-text>
            <n-form label-placement="left" label-width="200" style="max-width: 640px">
              <n-form-item label="Grading mode">
                <n-select
                  v-model:value="gradingForm.grading_mode"
                  :options="[{ label: 'Per Ion', value: 'per_ion' }, { label: 'Per Analysis', value: 'per_analysis' }]"
                />
              </n-form-item>
              <n-form-item :label="pointsLabel">
                <n-input-number v-model:value="gradingForm.points_per_correct_ion" :min="0" />
              </n-form-item>
              <n-form-item v-if="gradingForm.grading_mode === 'per_ion'" label="Penalty 2nd submission">
                <n-input-number v-model:value="gradingForm.penalty_second_submission" :min="0" />
              </n-form-item>
              <n-form-item v-if="gradingForm.grading_mode === 'per_ion'" label="Penalty 3rd submission">
                <n-input-number v-model:value="gradingForm.penalty_third_submission" :min="0" />
              </n-form-item>
              <n-form-item v-if="gradingForm.grading_mode === 'per_ion'" label="False positive deduction">
                <n-input-number v-model:value="gradingForm.false_positive_deduction" :min="0" />
              </n-form-item>
              <n-form-item v-if="gradingForm.grading_mode === 'per_analysis'" label=" " :show-label="false">
                <n-text depth="3" style="font-size: 12px">
                  Per-analysis mode is all-or-nothing: full points only when every ion is correct.
                  Retry penalties do not apply.
                </n-text>
              </n-form-item>
              <n-form-item label="Max submissions per analysis">
                <n-input-number v-model:value="gradingForm.max_submissions_per_analysis" :min="1" />
              </n-form-item>
              <n-form-item label="Final score strategy">
                <n-select
                  v-model:value="gradingForm.final_score_strategy"
                  :options="[{ label: 'Best', value: 'best' }, { label: 'Last', value: 'last' }]"
                />
              </n-form-item>
              <n-form-item label="Min. points to pass">
                <n-input-number v-model:value="gradingForm.passing_score" :min="0" />
              </n-form-item>
            </n-form>
            <n-button type="primary" size="small" :loading="gradingSaving" @click="saveGrading">
              Save Course Grading
            </n-button>
          </n-space>
        </template>

        <!-- Calendar: the course's analysis windows (week / month views). -->
        <template v-else-if="courseView === 'calendar'">
          <n-space vertical size="medium">
            <div class="cal-toolbar">
              <n-radio-group v-model:value="calendarView" size="small">
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

            <n-spin :show="loadingInstances">
              <n-empty v-if="!loadingInstances && courseInstances.length === 0" description="No analyses (windows) for this course yet." size="small" />

              <!-- WEEK VIEW: one row per analysis, a bar across the days it spans -->
              <div v-else-if="calendarView === 'week'" class="weekcal">
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
        </template>
      </div>
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

    <!-- Add / edit a student account -->
    <n-modal v-model:show="studentModal.show" preset="card" :title="studentModal.editing ? `Edit student — ${studentModal.form.username}` : 'Add student'" style="width: 520px; max-width: 94vw">
      <n-space vertical>
        <n-alert v-if="studentModal.generatedPassword" type="success" title="Student created">
          The initial (auto-generated) password is
          <code style="font-weight: 700">{{ studentModal.generatedPassword }}</code> — share it with the student and have them change it after first login.
        </n-alert>
        <n-form label-placement="left" label-width="130">
          <n-form-item label="Username">
            <n-input v-model:value="studentModal.form.username" placeholder="e.g. jdoe" />
          </n-form-item>
          <n-form-item :label="studentModal.editing ? 'New password' : 'Password'">
            <n-input
              v-model:value="studentModal.form.password"
              :placeholder="studentModal.editing ? 'Leave blank to keep the current password' : 'Leave blank to auto-generate'"
            />
          </n-form-item>
          <n-form-item label="Name">
            <n-input v-model:value="studentModal.form.name" placeholder="e.g. Jane Doe" />
          </n-form-item>
          <n-form-item label="Email">
            <n-input v-model:value="studentModal.form.email" placeholder="e.g. jane.doe@example.com" />
          </n-form-item>
          <n-form-item label="Matriculation no.">
            <n-input v-model:value="studentModal.form.matriculation_no" placeholder="e.g. M123456" />
          </n-form-item>
          <n-form-item label="Lab">
            <n-input v-model:value="studentModal.form.lab" placeholder="e.g. Inorganic Chemistry, Biology track" />
          </n-form-item>
          <n-form-item label="Labspace ID">
            <n-input v-model:value="studentModal.form.labspace_id" placeholder="e.g. LS-000123" />
          </n-form-item>
          <n-form-item label="Telephone">
            <n-input v-model:value="studentModal.form.telephone" placeholder="e.g. +49 151 2345678" />
          </n-form-item>
          <n-form-item v-if="!studentModal.editing" label="Course">
            <n-select v-model:value="studentModal.form.course_id" :options="courseOptions" clearable placeholder="No course" />
          </n-form-item>
          <n-form-item v-else label="Active">
            <n-switch v-model:value="studentModal.form.is_active" />
          </n-form-item>
        </n-form>
      </n-space>
      <template #footer>
        <n-space justify="end">
          <n-button @click="studentModal.show = false">Close</n-button>
          <n-button type="primary" :loading="studentModal.saving" @click="saveStudent">
            {{ studentModal.editing ? 'Save' : 'Create' }}
          </n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- Bulk student import (CSV) -->
    <n-modal v-model:show="importModal.show" preset="card" title="Import students (CSV)" style="width: 640px; max-width: 94vw">
      <n-space vertical>
        <n-text depth="3" style="font-size: 13px; display: block">
          Columns: username; name; email; matriculation_no; lab; labspace_id; telephone; course (course name);
          password (new students only — leave blank to auto-generate). Rows are matched by username: a match
          updates the existing student (password and an empty course are ignored), otherwise a new account is created.
        </n-text>
        <n-space align="center">
          <n-upload :file-list="importModal.fileList" :max="1" accept=".csv,text/csv" @update:file-list="onImportFileChange">
            <n-button size="small" :disabled="!!importModal.file">Choose CSV file</n-button>
          </n-upload>
          <n-button size="small" tertiary @click="downloadStudentTemplate">Download template</n-button>
        </n-space>
        <n-alert v-if="importModal.result" :type="importModal.result.errors.length ? 'warning' : 'success'" title="Import result" closable @close="importModal.result = null">
          <n-space vertical size="small">
            <n-text>
              {{ importModal.result.created }} created, {{ importModal.result.updated }} updated, {{ importModal.result.skipped }} skipped
              ({{ importModal.result.total_rows }} rows).
            </n-text>
            <template v-if="importModal.result.generated_passwords.length">
              <n-text depth="3">Auto-generated initial passwords:</n-text>
              <ul class="err-list">
                <li v-for="p in importModal.result.generated_passwords" :key="p.username">
                  <code style="font-weight: 700">{{ p.username }}: {{ p.password }}</code>
                </li>
              </ul>
            </template>
            <template v-if="importModal.result.errors.length">
              <n-text depth="3">Issues:</n-text>
              <ul class="err-list">
                <li v-for="(e, i) in importModal.result.errors" :key="i">{{ e }}</li>
              </ul>
            </template>
          </n-space>
        </n-alert>
      </n-space>
      <template #footer>
        <n-space justify="end">
          <n-button @click="importModal.show = false">Close</n-button>
          <n-button type="primary" :loading="importModal.uploading" :disabled="!importModal.file" @click="doImport">
            Upload &amp; import
          </n-button>
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
  NModal, NSwitch, NEmpty, NAlert, NRadioGroup, NRadioButton, NUpload, NSpin,
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

// Active tab of the course detail view: 'assign' | 'students' | 'analyses'
// | 'grading' | 'calendar'.
const courseView = ref('students')

// Per-course analysis instances (shared by the Analyses and Calendar tabs).
const courseInstances = ref([])
const loadingInstances = ref(false)

// Per-course grading settings (overrides the global default for one course).
const gradingForm = ref({
  points_per_correct_ion: 10,
  penalty_second_submission: 2,
  penalty_third_submission: 4,
  false_positive_deduction: 0,
  grading_mode: 'per_ion',
  max_submissions_per_analysis: 3,
  final_score_strategy: 'best',
  passing_score: 50,
})
const gradingSaving = ref(false)

// In per-analysis mode the same field holds the points per *completed*
// analysis, so the label adapts to the selected grading mode.
const pointsLabel = computed(
  () => (gradingForm.value.grading_mode === 'per_analysis' ? 'Points per analysis' : 'Points per correct ion'),
)

// Assign (enroll) students into the open course.
const assignStudentIds = ref([])
const assignSaving = ref(false)

// Calendar tab: 'week' (Gantt timeline) or 'month' (a classic month grid with
// one chip per analysis/day it covers).
const calendarView = ref('week')

const courseStudents = computed(() =>
  students.value.filter((s) => s.course_id === selected.value?.id),
)

// Students that can be enrolled into the open course. Everyone is a candidate
// (a student can be moved from one course to another); those already in the
// target course are flagged so the admin knows.
const assignableStudentOptions = computed(() =>
  students.value.map((s) => {
    const inTarget = s.course_id === selected.value?.id
    return {
      label: inTarget ? `${s.name || s.username} (already in course)` : `${s.name || s.username} (${s.course_name ? 'in ' + s.course_name : 'no course'})`,
      value: s.id,
      disabled: inTarget,
    }
  }),
)

const alreadyInCourseCount = computed(
  () => students.value.filter((s) => s.course_id === selected.value?.id).length,
)

// ---- add / edit a student account -------------------------------------------
const studentModal = ref({
  show: false,
  editing: false,
  saving: false,
  generatedPassword: null,
  form: {
    id: null,
    username: '',
    password: '',
    name: '',
    email: '',
    matriculation_no: '',
    lab: '',
    labspace_id: '',
    telephone: '',
    course_id: null,
    is_active: true,
  },
})

// ---- bulk student import (CSV) ------------------------------------------------
const importModal = ref({
  show: false,
  uploading: false,
  file: null,
  fileList: [],
  result: null,
})

const courseOptions = computed(() => courses.value.map((c) => ({ label: c.name, value: c.id })))

// Student table for the "Students — <course>" panel.
const studentCols = [
  { title: 'Name', key: 'name', render: (row) => row.name || '—' },
  { title: 'Username', key: 'username' },
  { title: 'Matriculation no.', key: 'matriculation_no', render: (row) => row.matriculation_no || '—' },
  { title: 'Labspace', key: 'labspace_id', render: (row) => row.labspace_id || '—' },
  { title: 'Telephone', key: 'telephone', render: (row) => row.telephone || '—' },
  { title: 'Active', key: 'is_active', render: (row) => (row.is_active ? '✓' : '—') },
  {
    title: 'Actions',
    key: 'actions',
    render: (row) =>
      h('div', { style: 'display:flex;gap:6px;flex-wrap:wrap' }, [
        h(NButton, { size: 'tiny', secondary: true, onClick: () => openEditStudent(row) }, () => 'Edit'),
        h(NButton, { size: 'tiny', tertiary: true, onClick: () => detachStudent(row) }, () => 'Detach'),
        h(NButton, { size: 'tiny', tertiary: true, type: 'error', onClick: () => deleteStudent(row) }, () => 'Delete'),
      ]),
  },
]

function openAddStudent() {
  studentModal.value = {
    show: true,
    editing: false,
    saving: false,
    generatedPassword: null,
    form: {
      id: null,
      username: '',
      password: '',
      name: '',
      email: '',
      matriculation_no: '',
      lab: '',
      labspace_id: '',
      telephone: '',
      course_id: selected.value?.id ?? null,
      is_active: true,
    },
  }
}

function openEditStudent(s) {
  studentModal.value = {
    show: true,
    editing: true,
    saving: false,
    generatedPassword: null,
    form: {
      id: s.id,
      username: s.username,
      password: '',
      name: s.name || '',
      email: s.email || '',
      matriculation_no: s.matriculation_no || '',
      lab: s.lab || '',
      labspace_id: s.labspace_id || '',
      telephone: s.telephone || '',
      course_id: s.course_id,
      is_active: s.is_active,
    },
  }
}

async function saveStudent() {
  const f = studentModal.value.form
  if (!f.username) {
    message.value = 'Username is required.'
    msgType.value = 'error'
    return
  }
  studentModal.value.saving = true
  try {
    if (studentModal.value.editing) {
      const payload = {
        username: f.username,
        name: f.name,
        email: f.email,
        matriculation_no: f.matriculation_no,
        lab: f.lab,
        labspace_id: f.labspace_id,
        telephone: f.telephone,
        is_active: f.is_active,
      }
      if (f.password) payload.password = f.password
      const res = await api.put(`/admin/students/${f.id}`, payload)
      message.value = f.password
        ? `Student ${res.username} updated (password reset).`
        : `Student ${res.username} updated.`
      studentModal.value.show = false
    } else {
      const res = await api.post('/admin/students', {
        username: f.username,
        password: f.password,
        name: f.name,
        email: f.email,
        matriculation_no: f.matriculation_no,
        lab: f.lab,
        labspace_id: f.labspace_id,
        telephone: f.telephone,
        course_id: f.course_id,
      })
      // Keep the modal open so an auto-generated initial password can be copied.
      if (res.password) studentModal.value.generatedPassword = res.password
      message.value = `Student ${res.username} created.`
    }
    msgType.value = 'success'
    await loadStudents()
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  } finally {
    studentModal.value.saving = false
  }
}

async function deleteStudent(s) {
  if (!confirm(`Delete student ${s.username} (including assignments and barcodes)? This cannot be undone.`)) return
  try {
    await api.delete(`/admin/students/${s.id}`)
    message.value = `Student ${s.username} deleted.`
    msgType.value = 'success'
    await loadStudents()
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  }
}

function openImport() {
  importModal.value = { show: true, uploading: false, file: null, fileList: [], result: null }
}

function onImportFileChange(list) {
  importModal.value.fileList = list
  importModal.value.file = list.length ? list[0].file : null
}

function downloadStudentTemplate() {
  api.download('/admin/students/import-template', 'students_import_template.csv').catch((e) => {
    message.value = e.message
    msgType.value = 'error'
  })
}

async function doImport() {
  if (!importModal.value.file) return
  importModal.value.uploading = true
  try {
    importModal.value.result = await api.upload('/admin/students/import-csv', importModal.value.file)
    await loadStudents()
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  } finally {
    importModal.value.uploading = false
  }
}

// ---- window calendar (week view) ---------------------------------------------
// Sort the course's analyses by their window start so the rows read in
// chronological order.
const calendarInstances = computed(() =>
  [...courseInstances.value].sort(
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
      ]),
  },
]

// Clickable course rows: opening a row selects the course and shows the
// detail view below the table (like the assistant's course view).
function courseRowProps(row) {
  return {
    style: 'cursor: pointer',
    class: row.id === selected.value?.id ? 'course-row--selected' : '',
    onClick: () => openCourseDetail(row),
  }
}

// Open the detail view for a course and preload all tab data.
function openCourseDetail(row, view = 'students') {
  selected.value = row
  courseView.value = view
  assignStudentIds.value = []
  loadStudents()
  loadCourseInstances(row.id)
  loadGrading(row.id)
}

function switchCourseView(view) {
  courseView.value = view
}

// Keep the open detail row in sync after the course list is refreshed
// (e.g. after creating or editing a course).
function refreshSelected() {
  if (!selected.value?.id) return
  selected.value = courses.value.find((c) => c.id === selected.value.id) ?? null
}

async function loadCourses() {
  loading.value = true
  try {
    courses.value = await api.get('/admin/courses')
    refreshSelected()
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  } finally {
    loading.value = false
  }
}

// Load the open course's analysis instances (shared by the Analyses and
// Calendar tabs).
async function loadCourseInstances(courseId = selected.value?.id) {
  if (!courseId) return
  loadingInstances.value = true
  try {
    courseInstances.value = await api.get(`/admin/analysis-instances?course_id=${courseId}`)
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  } finally {
    loadingInstances.value = false
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
async function loadGrading(courseId = selected.value?.id) {
  if (!courseId) return
  try {
    // The endpoint returns the course's own config or the global default, so the
    // form is always populated with usable starting values.
    gradingForm.value = await api.get(`/admin/courses/${courseId}/grading-config`)
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  }
}

async function saveGrading() {
  if (!selected.value) return
  gradingSaving.value = true
  try {
    gradingForm.value = await api.put(
      `/admin/courses/${selected.value.id}/grading-config`,
      gradingForm.value,
    )
    message.value = `Grading saved for ${selected.value.name}.`
    msgType.value = 'success'
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  } finally {
    gradingSaving.value = false
  }
}

// ---- assign (enroll) students into the open course -------------------------
async function saveAssign() {
  if (!selected.value || assignStudentIds.value.length === 0) return
  assignSaving.value = true
  let ok = 0
  try {
    for (const sid of assignStudentIds.value) {
      await api.put(`/admin/students/${sid}/course`, { student_id: sid, course_id: selected.value.id })
      ok += 1
    }
    message.value = `${ok} student${ok === 1 ? '' : 's'} assigned to ${selected.value.name}.`
    msgType.value = 'success'
    assignStudentIds.value = []
    // Refresh the student list; the "Students" tab (if open) re-filters itself.
    await loadStudents()
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  } finally {
    assignSaving.value = false
  }
}

// ---- analyses: open the per-course analysis-assignment workflow ------------
function goToAssignments() {
  // Reuse the Assignments page, pre-selecting this course via the query param.
  router.push({ name: 'admin-assignments', query: { course: String(selected.value.id) } })
}

// Window status label for the Analyses tab.
const STATUS_LABEL = { open: 'Open', too_early: 'Too early', too_late: 'Too late' }

// Columns for the course's analysis instances (Analyses tab).
const analysisCols = [
  { title: '#', key: 'number', render: (row) => `#${row.number}`, width: 56 },
  { title: 'Type', key: 'type' },
  {
    title: 'Window',
    key: 'window',
    render: (row) => `${fmt(row.window_start)} → ${fmt(row.window_end)}`,
  },
  { title: 'Status', key: 'status', render: (row) => STATUS_LABEL[windowStatus(row)] ?? windowStatus(row), width: 100 },
  {
    title: 'Students',
    key: 'assigned_students',
    render: (row) => h('span', { title: row.assigned_students.join(', ') || '—' }, String(row.assigned_students.length)),
    width: 90,
  },
]

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
.muted {
  font-size: var(--fc-fs-sm);
  font-weight: 400;
  color: var(--fc-muted);
}
/* Course detail view: tab navigation sits between the title and the view. */
.course-nav {
  margin-bottom: var(--fc-space-sm);
}
/* Selected course row (the detail view below shows its data). Rows render
   inside the data table, so the selectors need :deep(). */
:deep(.course-row--selected .n-data-table-td),
:deep(.course-row--selected:hover .n-data-table-td) {
  background: var(--fc-flame-soft);
}
/* Error / generated-password lists in the CSV import result. */
.err-list {
  margin: 4px 0 0 18px;
  font-size: var(--fc-fs-sm);
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
