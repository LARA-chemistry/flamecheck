<template>
  <n-space vertical size="large">
    <n-card size="small" :bordered="false">
      <div class="page-head">
        <h2 class="page-title">Multiple Choice</h2>
        <n-space size="small" align="center">
          <n-select
            v-model:value="courseFilter"
            :options="courseOptions"
            placeholder="All courses"
            clearable
            style="width: 240px"
            @update:value="loadAll"
          />
          <n-button type="primary" size="small" @click="openCardCreate">+ New Card</n-button>
        </n-space>
      </div>
      <n-text depth="3" class="hint">
        A card groups up to 3 questions into one graded unit; a sheet presents a card to
        assigned students inside a time window. Filter by course to narrow the lists (and to
        adjust the course's MC grading).
      </n-text>

      <!-- Cards: the main list (like the Analysis Types table). -->
      <n-data-table
        :columns="cardCols"
        :data="cards"
        size="small"
        :loading="loading.cards"
        :row-key="(row) => row.id"
        :row-props="(row) => ({ style: 'cursor: pointer', onClick: (e) => onCardRowClick(row, e) })"
      />
      <n-text depth="3" style="font-size: 12px">Click a row to edit the card; "Sheets" lists its time-windowed presentations.</n-text>

      <!-- Question bank. -->
      <div class="section-head">
        <h3 class="section-title">Question bank</h3>
        <n-button type="primary" size="small" @click="openQuestionCreate">+ New Question</n-button>
      </div>
      <n-data-table
        :columns="questionCols"
        :data="questions"
        size="small"
        :loading="loading.questions"
        :row-key="(row) => row.id"
        :row-props="(row) => ({ style: 'cursor: pointer', onClick: (e) => onQuestionRowClick(row, e) })"
      />

      <!-- Per-course MC grading (shown when a course is selected). -->
      <template v-if="courseFilter">
        <div class="section-head">
          <h3 class="section-title">Grading ({{ courseName }})</h3>
          <n-button size="small" type="primary" :loading="savingGrading" @click="saveGrading">Save Grading</n-button>
        </div>
        <n-text depth="3" class="hint">
          A fully correct card earns the points-per-card; each wrong answer deducts the penalty.
          Set the penalty to the points (e.g. 10 / 10) for a strict all-or-nothing card.
        </n-text>
        <n-space align="center" :wrap="true" style="margin-top: 8px">
          <n-form-item label="Points per card (all correct)" label-placement="left" style="margin-bottom: 0">
            <n-input-number v-model:value="grading.mc_points_per_card" :min="0" size="small" />
          </n-form-item>
          <n-form-item label="Penalty per wrong answer" label-placement="left" style="margin-bottom: 0">
            <n-input-number v-model:value="grading.mc_penalty_per_wrong" :min="0" size="small" />
          </n-form-item>
        </n-space>
      </template>
    </n-card>

    <!-- Card editor (like the Analysis Type editor). -->
    <n-modal v-model:show="cardModal.show" preset="card" :title="cardModal.editing ? 'Edit Card' : 'New Card'" style="width: 640px; max-width: 95vw">
      <n-form label-placement="left" label-width="120">
        <n-form-item label="Course">
          <n-select
            v-if="!cardModal.editing"
            v-model:value="cardModal.form.course_id"
            :options="courseOptions"
            placeholder="Select a course"
          />
          <n-text v-else>{{ cardModal.form.course_name }}</n-text>
        </n-form-item>
        <n-form-item label="Title">
          <n-input v-model:value="cardModal.form.title" placeholder="e.g. Flame test card 1" />
        </n-form-item>
        <n-form-item label="Questions">
          <n-space vertical size="small">
            <div v-for="(qid, i) in cardModal.form.question_ids" :key="i" class="option-row">
              <n-text depth="3" class="q-index">{{ i + 1 }}.</n-text>
              <n-select
                :value="qid"
                @update:value="(v) => (cardModal.form.question_ids[i] = v)"
                :options="cardQuestionOptions"
                placeholder="Select a question"
                filterable
                style="flex: 1"
              />
              <n-button
                size="small"
                quaternary
                type="error"
                :disabled="cardModal.form.question_ids.length <= 1"
                @click="cardModal.form.question_ids.splice(i, 1)"
              >
                Remove
              </n-button>
            </div>
            <n-button
              size="small"
              dashed
              :disabled="cardModal.form.question_ids.length >= 3"
              @click="cardModal.form.question_ids.push(null)"
            >
              + Add question (max 3)
            </n-button>
          </n-space>
        </n-form-item>
        <n-form-item label="Description">
          <n-input v-model:value="cardModal.form.description" type="textarea" :rows="2" placeholder="Documentation (admin only)" />
        </n-form-item>
        <n-form-item label="Remarks">
          <n-input v-model:value="cardModal.form.remarks" type="textarea" :rows="2" placeholder="Free remarks (admin only)" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button v-if="cardModal.editing" type="error" ghost @click="deleteCard">Delete</n-button>
          <n-button @click="cardModal.show = false">Cancel</n-button>
          <n-button type="primary" :loading="cardModal.saving" @click="saveCard">Save</n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- Question editor. -->
    <n-modal v-model:show="questionModal.show" preset="card" :title="questionModal.editing ? 'Edit Question' : 'New Question'" style="width: 680px; max-width: 95vw">
      <n-form label-placement="left" label-width="120" :show-require-mark="false">
        <n-form-item label="Course">
          <n-select
            v-if="!questionModal.editing"
            v-model:value="questionModal.form.course_id"
            :options="courseOptions"
            placeholder="Select a course"
          />
          <n-text v-else>{{ questionModal.form.course_name }}</n-text>
        </n-form-item>
        <n-form-item label="Question text">
          <n-input v-model:value="questionModal.form.text" type="textarea" :rows="2" placeholder="e.g. Which flame colour does sodium produce?" />
        </n-form-item>
        <n-form-item label="Options">
          <n-space vertical size="small">
            <n-radio-group v-model:value="questionModal.form.correctIndex">
              <div v-for="(opt, i) in questionModal.form.options" :key="i" class="option-row">
                <n-radio :value="i" />
                <n-input v-model:value="opt.text" placeholder="Option text" />
                <n-button
                  size="small"
                  quaternary
                  type="error"
                  :disabled="questionModal.form.options.length <= 2"
                  @click="removeOption(i)"
                >
                  Remove
                </n-button>
              </div>
            </n-radio-group>
            <n-button size="small" dashed @click="addOption">+ Add option</n-button>
            <n-text depth="3" style="font-size: 12px">Mark the correct option with the radio button.</n-text>
          </n-space>
        </n-form-item>
        <n-form-item label="Description">
          <n-input v-model:value="questionModal.form.description" type="textarea" :rows="2" placeholder="What the question covers, source, learning objective" />
        </n-form-item>
        <n-form-item label="Remarks">
          <n-input v-model:value="questionModal.form.remarks" type="textarea" :rows="2" placeholder="Grading notes, lab context, free remarks" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button v-if="questionModal.editing" type="error" ghost @click="deleteQuestion">Delete</n-button>
          <n-button @click="questionModal.show = false">Cancel</n-button>
          <n-button type="primary" :loading="questionModal.saving" @click="saveQuestion">Save</n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- Per-card sheets (like the per-type Sessions modal). -->
    <n-modal v-model:show="sheets.show" preset="card" :title="`Sheets — ${sheets.cardTitle}`" style="width: 820px; max-width: 96vw">
      <n-space vertical>
        <n-text depth="3" style="font-size: 13px">
          Each sheet presents the card inside its own time window to the assigned students.
          Use the pickers to adjust a sheet's window, or add a new sheet below.
        </n-text>
        <n-data-table :columns="sheetCols" :data="sheets.rows" size="small" :loading="sheets.loading" />
        <n-empty v-if="!sheets.loading && sheets.rows.length === 0" description="No sheets for this card yet." size="small" />

        <!-- New sheet row -->
        <div class="new-sheet">
          <n-text strong style="font-size: 13px">New sheet</n-text>
          <n-space align="center" :wrap="true">
            <n-input-number v-model:value="sheets.new.number" :min="1" size="small" style="width: 110px" placeholder="Announcement #" />
            <n-date-picker
              v-model:formatted-value="sheets.new.window_start"
              type="datetime"
              value-format="yyyy-MM-dd HH:mm"
              format="yyyy-MM-dd HH:mm"
              placeholder="Opens"
              size="small"
              style="width: 180px"
            />
            <n-date-picker
              v-model:formatted-value="sheets.new.window_end"
              type="datetime"
              value-format="yyyy-MM-dd HH:mm"
              format="yyyy-MM-dd HH:mm"
              placeholder="Closes"
              size="small"
              style="width: 180px"
            />
            <n-select
              v-model:value="sheets.new.student_ids"
              :options="sheetsStudentOptions"
              multiple
              filterable
              placeholder="Students (empty = nobody yet)"
              size="small"
              style="width: 280px"
              :loading="sheets.studentsLoading"
            />
            <n-button type="primary" size="small" :loading="sheets.new.saving" @click="createSheet">Add sheet</n-button>
          </n-space>
        </div>
      </n-space>
    </n-modal>

    <!-- Sheet editor (window / number / students of one sheet). -->
    <n-modal v-model:show="sheetEdit.show" preset="card" title="Edit Sheet" style="width: 640px; max-width: 95vw">
      <n-form label-placement="left" label-width="120">
        <n-form-item label="Card">
          <n-text>{{ sheetEdit.cardTitle }}</n-text>
        </n-form-item>
        <n-form-item label="Window">
          <div class="window-pair">
            <n-date-picker
              v-model:formatted-value="sheetEdit.form.window_start"
              type="datetime"
              value-format="yyyy-MM-dd HH:mm"
              format="yyyy-MM-dd HH:mm"
              placeholder="Opens"
              class="window-pair__picker"
            />
            <span class="window-pair__sep">→</span>
            <n-date-picker
              v-model:formatted-value="sheetEdit.form.window_end"
              type="datetime"
              value-format="yyyy-MM-dd HH:mm"
              format="yyyy-MM-dd HH:mm"
              placeholder="Closes"
              class="window-pair__picker"
            />
          </div>
        </n-form-item>
        <n-form-item label="Announcement #">
          <n-input-number v-model:value="sheetEdit.form.number" :min="1" :max="20" />
        </n-form-item>
        <n-form-item label="Students">
          <n-select
            v-model:value="sheetEdit.form.student_ids"
            :options="sheetEditStudentOptions"
            multiple
            filterable
            placeholder="Select students (empty = nobody yet)"
            :loading="sheetEdit.studentsLoading"
          />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button type="error" ghost @click="deleteSheet">Delete</n-button>
          <n-button @click="sheetEdit.show = false">Cancel</n-button>
          <n-button type="primary" :loading="sheetEdit.saving" @click="saveSheet">Save</n-button>
        </n-space>
      </template>
    </n-modal>

    <n-alert v-if="message" :type="msgType" closable @close="message = ''">{{ message }}</n-alert>
  </n-space>
</template>

<script setup>
import { ref, computed, watch, onMounted, h } from 'vue'
import { api } from '../api/client'
import {
  NSpace, NButton, NInput, NInputNumber, NSelect, NDataTable, NCard, NForm, NFormItem,
  NModal, NAlert, NEmpty, NText, NDatePicker, NRadioGroup, NRadio,
} from 'naive-ui'

const message = ref('')
const msgType = ref('success')

const courses = ref([])
const courseFilter = ref(null) // null = all courses
const courseOptions = computed(() => courses.value.map((c) => ({ label: c.name, value: c.id })))
const courseName = computed(() => courses.value.find((c) => c.id === courseFilter.value)?.name || '')

const loading = ref({ cards: true, questions: true })
const cards = ref([])
const questions = ref([])

const grading = ref({ mc_points_per_card: 10, mc_penalty_per_wrong: 2 })
const savingGrading = ref(false)

// Format an ISO datetime to the picker's "yyyy-MM-dd HH:mm" shape (local time).
function isoToPicker(iso) {
  if (!iso) return null
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return null
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}
// Convert a picker value (formatted string or ms timestamp) to an ISO string for the API.
function timestampToIso(v) {
  if (v == null) return null
  const d = new Date(typeof v === 'string' ? v.replace(' ', 'T') : v)
  return Number.isNaN(d.getTime()) ? null : d.toISOString()
}
function flash(msg, type) {
  message.value = msg
  msgType.value = type
}

// ---- cards ------------------------------------------------------------------
const cardCols = [
  { title: 'Title', key: 'title', render: (row) => row.title },
  { title: 'Course', key: 'course_name', render: (row) => row.course_name || '—' },
  { title: 'Questions', key: 'questions', render: (row) => row.questions.map((q) => q.text).join('  →  ') },
  { title: 'Sheets', key: 'sheet_count', width: 80, render: (row) => `${row.sheet_count ?? 0}` },
  {
    title: 'Actions',
    key: 'actions',
    render: (row) =>
      h('div', { style: 'display:flex;gap:6px;flex-wrap:wrap' }, [
        h(NButton, { size: 'tiny', type: 'primary', secondary: true, onClick: () => openCardEdit(row) }, () => 'Edit'),
        h(NButton, { size: 'tiny', secondary: true, onClick: () => openSheets(row) }, () => 'Sheets'),
      ]),
  },
]

// Questions available for a card slot: same course as the card being edited/created.
const cardQuestionOptions = computed(() => {
  const courseId = cardModal.value.form.course_id
  return questions.value.filter((q) => q.course_id === courseId).map((q) => ({ label: q.text, value: q.id }))
})

const cardModal = ref({
  show: false,
  editing: false,
  saving: false,
  form: { id: null, course_id: null, course_name: '', title: '', description: '', remarks: '', question_ids: [null] },
})

function onCardRowClick(row, event) {
  if (event && event.target.closest('button, a')) return
  openCardEdit(row)
}

function openCardCreate() {
  cardModal.value = {
    show: true,
    editing: false,
    saving: false,
    form: { id: null, course_id: courseFilter.value, course_name: '', title: '', description: '', remarks: '', question_ids: [null] },
  }
}

function openCardEdit(row) {
  cardModal.value = {
    show: true,
    editing: true,
    saving: false,
    form: {
      id: row.id,
      course_id: row.course_id,
      course_name: row.course_name,
      title: row.title,
      description: row.description || '',
      remarks: row.remarks || '',
      question_ids: row.questions.length ? row.questions.map((q) => q.id) : [null],
    },
  }
}

async function saveCard() {
  const f = cardModal.value.form
  if (!f.course_id) return flash('Select a course.', 'error')
  if (!f.title) return flash('Title is required.', 'error')
  if (f.question_ids.some((id) => id == null)) return flash('Select a question for every slot.', 'error')
  cardModal.value.saving = true
  try {
    const payload = { title: f.title, description: f.description, remarks: f.remarks, question_ids: f.question_ids }
    if (cardModal.value.editing) await api.put(`/admin/multichoice/cards/${f.id}`, payload)
    else await api.post(`/admin/multichoice/cards?course_id=${f.course_id}`, payload)
    flash('Card saved.', 'success')
    cardModal.value.show = false
    await loadAll()
  } catch (e) {
    flash(e.message, 'error')
  } finally {
    cardModal.value.saving = false
  }
}

async function deleteCard() {
  const f = cardModal.value.form
  if (!confirm(`Delete card "${f.title}"?`)) return
  try {
    await api.delete(`/admin/multichoice/cards/${f.id}`)
    flash('Card deleted.', 'success')
    cardModal.value.show = false
    await loadAll()
  } catch (e) {
    flash(e.message, 'error')
  }
}

// ---- questions ----------------------------------------------------------------
const questionCols = [
  { title: 'Question', key: 'text', render: (row) => row.text },
  { title: 'Course', key: 'course_name', render: (row) => row.course_name || '—' },
  { title: 'Options', key: 'options', width: 140, render: (row) => `${row.options.length} (1 correct)` },
  { title: 'Cards', key: 'card_count', width: 80, render: (row) => row.card_count ?? 0 },
  {
    title: 'Actions',
    key: 'actions',
    render: (row) =>
      h('div', { style: 'display:flex;gap:6px;flex-wrap:wrap' }, [
        h(NButton, { size: 'tiny', type: 'primary', secondary: true, onClick: () => openQuestionEdit(row) }, () => 'Edit'),
      ]),
  },
]

const questionModal = ref({
  show: false,
  editing: false,
  saving: false,
  form: { id: null, course_id: null, course_name: '', text: '', description: '', remarks: '', options: [], correctIndex: 0 },
})

function onQuestionRowClick(row, event) {
  if (event && event.target.closest('button, a')) return
  openQuestionEdit(row)
}

function openQuestionCreate() {
  questionModal.value = {
    show: true,
    editing: false,
    saving: false,
    form: { id: null, course_id: courseFilter.value, course_name: '', text: '', description: '', remarks: '', options: [{ text: '' }, { text: '' }], correctIndex: 0 },
  }
}

function openQuestionEdit(row) {
  questionModal.value = {
    show: true,
    editing: true,
    saving: false,
    form: {
      id: row.id,
      course_id: row.course_id,
      course_name: row.course_name,
      text: row.text,
      description: row.description || '',
      remarks: row.remarks || '',
      options: row.options.map((o) => ({ text: o.text })),
      correctIndex: Math.max(0, row.options.findIndex((o) => o.is_correct)),
    },
  }
}

function addOption() {
  questionModal.value.form.options.push({ text: '' })
}

function removeOption(i) {
  questionModal.value.form.options.splice(i, 1)
  if (questionModal.value.form.correctIndex >= questionModal.value.form.options.length) {
    questionModal.value.form.correctIndex = Math.max(0, questionModal.value.form.options.length - 1)
  }
}

async function saveQuestion() {
  const f = questionModal.value.form
  if (!f.course_id) return flash('Select a course.', 'error')
  if (!f.text) return flash('Question text is required.', 'error')
  if (f.options.length < 2 || f.options.some((o) => !o.text)) return flash('Add at least two non-empty options.', 'error')
  questionModal.value.saving = true
  try {
    const options = f.options.map((o, i) => ({ text: o.text, is_correct: i === f.correctIndex, sort_order: i }))
    const payload = { text: f.text, description: f.description, remarks: f.remarks, options }
    if (questionModal.value.editing) await api.put(`/admin/multichoice/questions/${f.id}`, payload)
    else await api.post(`/admin/multichoice/questions?course_id=${f.course_id}`, payload)
    flash('Question saved.', 'success')
    questionModal.value.show = false
    await loadAll()
  } catch (e) {
    flash(e.message, 'error')
  } finally {
    questionModal.value.saving = false
  }
}

async function deleteQuestion() {
  const f = questionModal.value.form
  if (!confirm('Delete this question?')) return
  try {
    await api.delete(`/admin/multichoice/questions/${f.id}`)
    flash('Question deleted.', 'success')
    questionModal.value.show = false
    await loadAll()
  } catch (e) {
    flash(e.message, 'error')
  }
}

// ---- per-card sheets (like the per-type Sessions modal) -----------------------
const sheets = ref({
  show: false,
  loading: false,
  cardId: null,
  cardTitle: '',
  courseId: null,
  rows: [],
  students: [],
  studentsLoading: false,
  new: { number: 1, window_start: null, window_end: null, student_ids: [], saving: false },
})

const sheetsStudentOptions = computed(() => sheets.value.students.map((s) => ({ label: s.full_name || s.username, value: s.id })))

// Sheet rows with inline window pickers (like the session windows table).
const sheetCols = [
  { title: '№', key: 'number', width: 44, render: (row) => `#${row.number}` },
  {
    title: 'Window opens',
    key: 'window_start',
    render: (row) =>
      h(NDatePicker, {
        formattedValue: isoToPicker(row.window_start),
        type: 'datetime',
        'value-format': 'yyyy-MM-dd HH:mm',
        format: 'yyyy-MM-dd HH:mm',
        size: 'small',
        style: 'width: 170px',
        'onUpdate:formattedValue': (v) => updateSheetWindow(row, 'window_start', v),
      }),
  },
  {
    title: 'Window closes',
    key: 'window_end',
    render: (row) =>
      h(NDatePicker, {
        formattedValue: isoToPicker(row.window_end),
        type: 'datetime',
        'value-format': 'yyyy-MM-dd HH:mm',
        format: 'yyyy-MM-dd HH:mm',
        size: 'small',
        style: 'width: 170px',
        'onUpdate:formattedValue': (v) => updateSheetWindow(row, 'window_end', v),
      }),
  },
  { title: 'Students', key: 'student_ids', width: 80, render: (row) => `${row.student_ids.length}` },
  { title: 'Submissions', key: 'submission_count', width: 100, render: (row) => row.submission_count ?? 0 },
  {
    title: 'Actions',
    key: 'actions',
    render: (row) =>
      h('div', { style: 'display:flex;gap:6px;flex-wrap:wrap' }, [
        h(NButton, { size: 'tiny', secondary: true, onClick: () => openSheetEdit(row) }, () => 'Edit'),
      ]),
  },
]

async function openSheets(row) {
  sheets.value.show = true
  sheets.value.cardId = row.id
  sheets.value.cardTitle = row.title
  sheets.value.courseId = row.course_id
  sheets.value.rows = []
  sheets.value.loading = true
  sheets.value.students = []
  sheets.value.new = { number: 1, window_start: null, window_end: null, student_ids: [], saving: false }
  await Promise.all([loadSheetRows(), loadSheetStudents()])
  sheets.value.loading = false
}

async function loadSheetRows() {
  try {
    sheets.value.rows = await api.get(`/admin/multichoice/sheets?card_id=${sheets.value.cardId}`)
  } catch (e) {
    flash(e.message, 'error')
  }
}

async function loadSheetStudents() {
  if (!sheets.value.courseId) return
  sheets.value.studentsLoading = true
  try {
    sheets.value.students = await api.get(`/admin/students?course_id=${sheets.value.courseId}`)
  } catch (e) {
    /* ignore */
  } finally {
    sheets.value.studentsLoading = false
  }
}

async function updateSheetWindow(row, field, value) {
  row[field] = value ? timestampToIso(value) : null
  try {
    await api.put(`/admin/multichoice/sheets/${row.id}`, {
      card_id: sheets.value.cardId,
      course_id: sheets.value.courseId,
      window_start: row.window_start,
      window_end: row.window_end,
      number: row.number,
      student_ids: row.student_ids,
    })
    flash('Window saved.', 'success')
  } catch (e) {
    flash(e.message, 'error')
  }
}

async function createSheet() {
  const n = sheets.value.new
  if (!n.window_start || !n.window_end) return flash('Set both window times for the new sheet.', 'error')
  if (new Date(n.window_start.replace(' ', 'T')) >= new Date(n.window_end.replace(' ', 'T'))) {
    return flash('The sheet window must close after it opens.', 'error')
  }
  n.saving = true
  try {
    await api.post('/admin/multichoice/sheets', {
      card_id: sheets.value.cardId,
      course_id: sheets.value.courseId,
      window_start: timestampToIso(n.window_start),
      window_end: timestampToIso(n.window_end),
      number: n.number,
      student_ids: n.student_ids,
    })
    flash(`Sheet #${n.number} added.`, 'success')
    await loadSheetRows()
    n.window_start = null
    n.window_end = null
    n.student_ids = []
  } catch (e) {
    flash(e.message, 'error')
  } finally {
    n.saving = false
  }
}

// ---- sheet editor modal -------------------------------------------------------
const sheetEdit = ref({
  show: false,
  saving: false,
  cardTitle: '',
  courseId: null,
  students: [],
  studentsLoading: false,
  form: { id: null, window_start: null, window_end: null, number: 1, student_ids: [] },
})

const sheetEditStudentOptions = computed(() => sheetEdit.value.students.map((s) => ({ label: s.full_name || s.username, value: s.id })))

async function openSheetEdit(row) {
  sheetEdit.value.show = true
  sheetEdit.value.saving = false
  sheetEdit.value.cardTitle = sheets.value.cardTitle
  sheetEdit.value.courseId = row.course_id ?? sheets.value.courseId
  sheetEdit.value.students = []
  sheetEdit.value.form = {
    id: row.id,
    window_start: isoToPicker(row.window_start),
    window_end: isoToPicker(row.window_end),
    number: row.number,
    student_ids: [...row.student_ids],
  }
  sheetEdit.value.studentsLoading = true
  try {
    sheetEdit.value.students = await api.get(`/admin/students?course_id=${sheetEdit.value.courseId}`)
  } catch (e) {
    /* ignore */
  } finally {
    sheetEdit.value.studentsLoading = false
  }
}

async function saveSheet() {
  const f = sheetEdit.value.form
  if (!f.window_start || !f.window_end) return flash('Set both window times.', 'error')
  sheetEdit.value.saving = true
  try {
    await api.put(`/admin/multichoice/sheets/${f.id}`, {
      card_id: sheets.value.cardId,
      course_id: sheetEdit.value.courseId,
      window_start: timestampToIso(f.window_start),
      window_end: timestampToIso(f.window_end),
      number: f.number,
      student_ids: f.student_ids,
    })
    flash('Sheet saved.', 'success')
    sheetEdit.value.show = false
    await loadSheetRows()
  } catch (e) {
    flash(e.message, 'error')
  } finally {
    sheetEdit.value.saving = false
  }
}

async function deleteSheet() {
  const f = sheetEdit.value.form
  if (!confirm('Delete this sheet? Sheets with submissions cannot be deleted.')) return
  try {
    await api.delete(`/admin/multichoice/sheets/${f.id}`)
    flash('Sheet deleted.', 'success')
    sheetEdit.value.show = false
    await loadSheetRows()
  } catch (e) {
    flash(e.message, 'error')
  }
}

// ---- grading (per selected course) ---------------------------------------------
async function loadGrading() {
  if (!courseFilter.value) return
  try {
    const g = await api.get(`/admin/courses/${courseFilter.value}/grading-config`)
    grading.value = { mc_points_per_card: g.mc_points_per_card, mc_penalty_per_wrong: g.mc_penalty_per_wrong }
  } catch (e) {
    /* defaults stay */
  }
}

async function saveGrading() {
  savingGrading.value = true
  try {
    const current = await api.get(`/admin/courses/${courseFilter.value}/grading-config`)
    await api.put(`/admin/courses/${courseFilter.value}/grading-config`, { ...current, ...grading.value })
    flash('Grading saved.', 'success')
  } catch (e) {
    flash(e.message, 'error')
  } finally {
    savingGrading.value = false
  }
}

watch(courseFilter, loadGrading)

// ---- data loading ---------------------------------------------------------------
async function loadCourses() {
  try {
    courses.value = await api.get('/admin/courses')
  } catch (e) {
    /* ignore */
  }
}

async function loadCards() {
  loading.value.cards = true
  try {
    const url = courseFilter.value
      ? `/admin/multichoice/cards?course_id=${courseFilter.value}`
      : '/admin/multichoice/cards'
    cards.value = await api.get(url)
  } catch (e) {
    flash(e.message, 'error')
  } finally {
    loading.value.cards = false
  }
}

async function loadQuestions() {
  loading.value.questions = true
  try {
    const url = courseFilter.value
      ? `/admin/multichoice/questions?course_id=${courseFilter.value}`
      : '/admin/multichoice/questions'
    questions.value = await api.get(url)
  } catch (e) {
    flash(e.message, 'error')
  } finally {
    loading.value.questions = false
  }
}

function loadAll() {
  loadCards()
  loadQuestions()
}

onMounted(() => {
  loadCourses()
  loadAll()
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
.hint {
  font-size: var(--fc-fs-sm);
}
.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: var(--fc-space-lg);
  margin-bottom: var(--fc-space-xs);
}
.section-title {
  font-size: var(--fc-fs-sm);
  font-weight: 700;
  color: var(--fc-ink);
}
.option-row {
  display: flex;
  align-items: center;
  gap: var(--fc-space-xs);
}
.q-index {
  min-width: 18px;
}
.window-pair {
  display: flex;
  align-items: center;
  gap: var(--fc-space-xs);
  flex-wrap: wrap;
}
.window-pair__picker {
  width: 210px;
}
.window-pair__sep {
  color: var(--fc-text-soft);
}
.new-sheet {
  padding-top: var(--fc-space-xs);
  border-top: 1px solid var(--fc-border);
  display: flex;
  flex-direction: column;
  gap: var(--fc-space-xs);
}
</style>
