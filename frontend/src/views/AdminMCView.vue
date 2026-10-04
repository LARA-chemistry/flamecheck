<template>
  <n-space vertical size="large">
    <!-- Course selector + per-course grading -->
    <n-card size="small" :bordered="false">
      <div class="page-head">
        <h2 class="page-title">Multiple Choice</h2>
        <n-select
          v-model:value="courseId"
          :options="courseOptions"
          placeholder="Select a course"
          style="width: 320px"
          @update:value="onCourseChange"
        />
      </div>
      <n-empty v-if="!courseId" description="Select a course to manage its questions, cards and sheets." />
      <n-space v-else vertical size="small">
        <n-text depth="3" class="hint">
          Define questions, group them into cards (max 3 questions each), and present
          time-windowed sheets to students. Grading below applies to this course only.
        </n-text>
        <n-space align="center" :wrap="true">
          <n-form-item label="Points per card (all correct)" label-placement="left" style="margin-bottom: 0">
            <n-input-number v-model:value="grading.mc_points_per_card" :min="0" size="small" />
          </n-form-item>
          <n-form-item label="Penalty per wrong answer" label-placement="left" style="margin-bottom: 0">
            <n-input-number v-model:value="grading.mc_penalty_per_wrong" :min="0" size="small" />
          </n-form-item>
          <n-button size="small" type="primary" :loading="savingGrading" @click="saveGrading">
            Save Grading
          </n-button>
        </n-space>
      </n-space>
    </n-card>

    <!-- Questions -->
    <n-card v-if="courseId" size="small" :bordered="false">
      <div class="page-head">
        <h3 class="section-title">Questions</h3>
        <n-button type="primary" size="small" @click="openQuestionCreate">+ New Question</n-button>
      </div>
      <n-data-table :columns="questionCols" :data="questions" size="small" :loading="loading.questions" />
    </n-card>

    <!-- Cards -->
    <n-card v-if="courseId" size="small" :bordered="false">
      <div class="page-head">
        <h3 class="section-title">Cards (max 3 questions each)</h3>
        <n-button type="primary" size="small" :disabled="!questions.length" @click="openCardCreate">+ New Card</n-button>
      </div>
      <n-data-table :columns="cardCols" :data="cards" size="small" :loading="loading.cards" />
    </n-card>

    <!-- Sheets -->
    <n-card v-if="courseId" size="small" :bordered="false">
      <div class="page-head">
        <h3 class="section-title">Sheets (time-windowed, assigned to students)</h3>
        <n-button type="primary" size="small" :disabled="!cards.length" @click="openSheetCreate">+ New Sheet</n-button>
      </div>
      <n-data-table :columns="sheetCols" :data="sheets" size="small" :loading="loading.sheets" />
    </n-card>

    <!-- Question modal -->
    <n-modal v-model:show="questionModal.show" preset="card" :title="questionModal.editing ? 'Edit Question' : 'New Question'" style="width: 680px; max-width: 95vw">
      <n-form label-placement="top" :show-require-mark="false">
        <n-form-item label="Question text">
          <n-input v-model:value="questionModal.form.text" type="textarea" :rows="2" placeholder="e.g. Which flame colour does sodium produce?" />
        </n-form-item>
        <n-form-item label="Options (select the correct one)">
          <n-space vertical size="small">
            <n-radio-group v-model:value="questionModal.form.correctIndex">
              <div v-for="(opt, i) in questionModal.form.options" :key="i" class="option-row">
                <n-radio :value="i" />
                <n-input v-model:value="opt.text" placeholder="Option text" />
                <n-button size="small" quaternary type="error" :disabled="questionModal.form.options.length <= 2" @click="removeOption(i)">Remove</n-button>
              </div>
            </n-radio-group>
            <n-button size="small" dashed @click="addOption">+ Add option</n-button>
          </n-space>
        </n-form-item>
        <n-form-item label="Description (documentation, admin only)">
          <n-input v-model:value="questionModal.form.description" type="textarea" :rows="2" placeholder="What the question covers, source, learning objective" />
        </n-form-item>
        <n-form-item label="Remarks (documentation, admin only)">
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

    <!-- Card modal -->
    <n-modal v-model:show="cardModal.show" preset="card" :title="cardModal.editing ? 'Edit Card' : 'New Card'" style="width: 640px; max-width: 95vw">
      <n-form label-placement="top">
        <n-form-item label="Title">
          <n-input v-model:value="cardModal.form.title" placeholder="e.g. Flame test card 1" />
        </n-form-item>
        <n-form-item label="Questions (1 to 3, in order)">
          <n-space vertical size="small">
            <div v-for="(qid, i) in cardModal.form.question_ids" :key="i" class="option-row">
              <n-text depth="3" class="q-index">{{ i + 1 }}.</n-text>
              <n-select :value="qid" @update:value="(v) => (cardModal.form.question_ids[i] = v)" :options="questionOptions" placeholder="Select a question" filterable style="flex: 1" />
              <n-button size="small" quaternary type="error" :disabled="cardModal.form.question_ids.length <= 1" @click="cardModal.form.question_ids.splice(i, 1)">Remove</n-button>
            </div>
            <n-button size="small" dashed :disabled="cardModal.form.question_ids.length >= 3" @click="cardModal.form.question_ids.push(null)">+ Add question (max 3)</n-button>
          </n-space>
        </n-form-item>
        <n-form-item label="Description (documentation, admin only)">
          <n-input v-model:value="cardModal.form.description" type="textarea" :rows="2" />
        </n-form-item>
        <n-form-item label="Remarks (documentation, admin only)">
          <n-input v-model:value="cardModal.form.remarks" type="textarea" :rows="2" />
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

    <!-- Sheet modal -->
    <n-modal v-model:show="sheetModal.show" preset="card" :title="sheetModal.editing ? 'Edit Sheet' : 'New Sheet'" style="width: 680px; max-width: 95vw">
      <n-form label-placement="top">
        <n-form-item label="Card">
          <n-select v-model:value="sheetModal.form.card_id" :options="cardOptions" placeholder="Select the card to present" filterable />
        </n-form-item>
        <n-form-item label="Submission window">
          <div class="window-pair">
            <n-date-picker v-model:formatted-value="sheetModal.form.window_start" type="datetime" value-format="yyyy-MM-dd HH:mm" format="yyyy-MM-dd HH:mm" placeholder="Opens" class="window-pair__picker" />
            <span class="window-pair__sep">→</span>
            <n-date-picker v-model:formatted-value="sheetModal.form.window_end" type="datetime" value-format="yyyy-MM-dd HH:mm" format="yyyy-MM-dd HH:mm" placeholder="Closes" class="window-pair__picker" />
          </div>
        </n-form-item>
        <n-form-item label="Announcement number">
          <n-input-number v-model:value="sheetModal.form.number" :min="1" :max="20" />
        </n-form-item>
        <n-form-item label="Assigned students">
          <n-select v-model:value="sheetModal.form.student_ids" :options="studentOptions" multiple filterable placeholder="Select students (empty = nobody yet)" :loading="loading.students" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button v-if="sheetModal.editing" type="error" ghost @click="deleteSheet">Delete</n-button>
          <n-button @click="sheetModal.show = false">Cancel</n-button>
          <n-button type="primary" :loading="sheetModal.saving" @click="saveSheet">Save</n-button>
        </n-space>
      </template>
    </n-modal>

    <n-alert v-if="message" :type="msgType" closable @close="message = ''">{{ message }}</n-alert>
  </n-space>
</template>

<script setup>
import { ref, onMounted, watch, h } from 'vue'
import { api } from '../api/client'
import {
  NSpace, NButton, NCard, NDataTable, NSelect, NInput, NInputNumber, NForm, NFormItem,
  NModal, NAlert, NEmpty, NText, NDatePicker, NRadioGroup, NRadio,
} from 'naive-ui'

const message = ref('')
const msgType = ref('success')
const courseId = ref(null)

const courses = ref([])
const questions = ref([])
const cards = ref([])
const sheets = ref([])
const students = ref([])
const loading = ref({ questions: true, cards: true, sheets: true, students: false })
const grading = ref({ mc_points_per_card: 10, mc_penalty_per_wrong: 2 })
const savingGrading = ref(false)

const courseOptions = () => courses.value.map((c) => ({ label: c.name, value: c.id }))
const questionOptions = () => questions.value.map((q) => ({ label: q.text, value: q.id }))
const cardOptions = () => cards.value.map((c) => ({ label: c.title, value: c.id }))
const studentOptions = () => students.value.map((s) => ({ label: s.full_name || s.username, value: s.id }))

// --- tables ---------------------------------------------------------------
const questionCols = [
  { title: 'Question', key: 'text', render: (row) => row.text },
  { title: 'Options', key: 'options', render: (row) => `${row.options.length} (1 correct)` },
  { title: 'Description', key: 'description', ellipsis: { tooltip: true }, render: (row) => row.description || '-' },
  { title: 'Cards', key: 'card_count', render: (row) => row.card_count },
  {
    title: 'Actions',
    key: 'actions',
    render: (row) =>
      h('div', { class: 'row-actions' }, [
        h(NButton, { size: 'small', secondary: true, onClick: () => openQuestionEdit(row) }, () => 'Edit'),
      ]),
  },
]
const cardCols = [
  { title: 'Title', key: 'title', render: (row) => row.title },
  { title: 'Questions', key: 'questions', render: (row) => row.questions.map((q) => q.text).join('  →  ') },
  { title: 'Sheets', key: 'sheet_count', render: (row) => row.sheet_count },
  {
    title: 'Actions',
    key: 'actions',
    render: (row) =>
      h('div', { class: 'row-actions' }, [
        h(NButton, { size: 'small', secondary: true, onClick: () => openCardEdit(row) }, () => 'Edit'),
      ]),
  },
]
const sheetCols = [
  { title: 'Card', key: 'card_title', render: (row) => row.card_title },
  { title: '№', key: 'number', render: (row) => row.number },
  { title: 'Window (opens)', key: 'window_start', render: (row) => fmt(row.window_start) },
  { title: 'Window (closes)', key: 'window_end', render: (row) => fmt(row.window_end) },
  { title: 'Students', key: 'student_ids', render: (row) => `${row.student_ids.length}` },
  { title: 'Submissions', key: 'submission_count', render: (row) => row.submission_count },
  {
    title: 'Actions',
    key: 'actions',
    render: (row) =>
      h('div', { class: 'row-actions' }, [
        h(NButton, { size: 'small', secondary: true, onClick: () => openSheetEdit(row) }, () => 'Edit'),
      ]),
  },
]

function fmt(iso) {
  if (!iso) return '-'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString()
}

// --- question modal -------------------------------------------------------
const questionModal = ref({
  show: false, editing: false, saving: false,
  form: { id: null, text: '', description: '', remarks: '', options: [], correctIndex: 0 },
})

function addOption() {
  questionModal.value.form.options.push({ text: '' })
}
function removeOption(i) {
  questionModal.value.form.options.splice(i, 1)
}
// Keep correctIndex in sync when an option is removed.
watch(
  () => questionModal.value.form.options.length,
  (len) => {
    if (questionModal.value.form.correctIndex >= len) questionModal.value.form.correctIndex = Math.max(0, len - 1)
  }
)

function openQuestionCreate() {
  questionModal.value = {
    show: true, editing: false, saving: false,
    form: { id: null, text: '', description: '', remarks: '', options: [{ text: '' }, { text: '' }], correctIndex: 0 },
  }
}
function openQuestionEdit(row) {
  questionModal.value = {
    show: true, editing: true, saving: false,
    form: {
      id: row.id,
      text: row.text,
      description: row.description,
      remarks: row.remarks,
      options: row.options.map((o) => ({ text: o.text })),
      correctIndex: Math.max(0, row.options.findIndex((o) => o.is_correct)),
    },
  }
}
async function saveQuestion() {
  const f = questionModal.value.form
  if (!f.text) return flash('Question text is required.', 'error')
  if (f.options.length < 2 || f.options.some((o) => !o.text)) return flash('Add at least two non-empty options.', 'error')
  questionModal.value.saving = true
  try {
    const options = f.options.map((o, i) => ({ text: o.text, is_correct: i === f.correctIndex, sort_order: i }))
    const payload = { text: f.text, description: f.description, remarks: f.remarks }
    if (f.editing) {
      payload.options = options
      await api.put(`/admin/multichoice/questions/${f.id}`, payload)
    } else {
      payload.options = options
      await api.post(`/admin/multichoice/questions?course_id=${courseId.value}`, payload)
    }
    flash('Question saved.', 'success')
    questionModal.value.show = false
    await loadQuestions()
  } catch (e) {
    flash(e.message, 'error')
  } finally {
    questionModal.value.saving = false
  }
}
async function deleteQuestion() {
  const f = questionModal.value.form
  try {
    await api.delete(`/admin/multichoice/questions/${f.id}`)
    flash('Question deleted.', 'success')
    questionModal.value.show = false
    await loadQuestions()
  } catch (e) {
    flash(e.message, 'error')
  }
}

// --- card modal -----------------------------------------------------------
const cardModal = ref({
  show: false, editing: false, saving: false,
  form: { id: null, title: '', description: '', remarks: '', question_ids: [null] },
})
function openCardCreate() {
  cardModal.value = {
    show: true, editing: false, saving: false,
    form: { id: null, title: '', description: '', remarks: '', question_ids: [null] },
  }
}
function openCardEdit(row) {
  cardModal.value = {
    show: true, editing: true, saving: false,
    form: {
      id: row.id, title: row.title, description: row.description, remarks: row.remarks,
      question_ids: row.questions.map((q) => q.id),
    },
  }
}
async function saveCard() {
  const f = cardModal.value.form
  if (!f.title) return flash('Title is required.', 'error')
  if (f.question_ids.some((id) => id == null)) return flash('Select a question for every slot.', 'error')
  cardModal.value.saving = true
  try {
    const payload = { title: f.title, description: f.description, remarks: f.remarks, question_ids: f.question_ids }
    if (f.editing) await api.put(`/admin/multichoice/cards/${f.id}`, payload)
    else await api.post(`/admin/multichoice/cards?course_id=${courseId.value}`, payload)
    flash('Card saved.', 'success')
    cardModal.value.show = false
    await loadCards()
  } catch (e) {
    flash(e.message, 'error')
  } finally {
    cardModal.value.saving = false
  }
}
async function deleteCard() {
  const f = cardModal.value.form
  try {
    await api.delete(`/admin/multichoice/cards/${f.id}`)
    flash('Card deleted.', 'success')
    cardModal.value.show = false
    await loadCards()
  } catch (e) {
    flash(e.message, 'error')
  }
}

// --- sheet modal ----------------------------------------------------------
const sheetModal = ref({
  show: false, editing: false, saving: false,
  form: { id: null, card_id: null, window_start: null, window_end: null, number: 1, student_ids: [] },
})
function openSheetCreate() {
  sheetModal.value = {
    show: true, editing: false, saving: false,
    form: { id: null, card_id: null, window_start: null, window_end: null, number: 1, student_ids: [] },
  }
}
function openSheetEdit(row) {
  sheetModal.value = {
    show: true, editing: true, saving: false,
    form: {
      id: row.id, card_id: row.card_id,
      window_start: toLocal(row.window_start), window_end: toLocal(row.window_end),
      number: row.number, student_ids: row.student_ids,
    },
  }
}
// Convert an ISO string to the "yyyy-MM-dd HH:mm" format the picker expects.
function toLocal(iso) {
  if (!iso) return null
  const d = new Date(iso)
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}
async function saveSheet() {
  const f = sheetModal.value.form
  if (!f.card_id) return flash('Select a card.', 'error')
  if (!f.window_start || !f.window_end) return flash('Set both window times.', 'error')
  sheetModal.value.saving = true
  try {
    const payload = {
      card_id: f.card_id, course_id: courseId.value,
      window_start: f.window_start, window_end: f.window_end,
      number: f.number, student_ids: f.student_ids,
    }
    if (f.editing) await api.put(`/admin/multichoice/sheets/${f.id}`, payload)
    else await api.post('/admin/multichoice/sheets', payload)
    flash('Sheet saved.', 'success')
    sheetModal.value.show = false
    await loadSheets()
  } catch (e) {
    flash(e.message, 'error')
  } finally {
    sheetModal.value.saving = false
  }
}
async function deleteSheet() {
  const f = sheetModal.value.form
  try {
    await api.delete(`/admin/multichoice/sheets/${f.id}`)
    flash('Sheet deleted.', 'success')
    sheetModal.value.show = false
    await loadSheets()
  } catch (e) {
    flash(e.message, 'error')
  }
}

// --- grading --------------------------------------------------------------
async function loadGrading() {
  try {
    const g = await api.get(`/admin/courses/${courseId.value}/grading-config`)
    grading.value = { mc_points_per_card: g.mc_points_per_card, mc_penalty_per_wrong: g.mc_penalty_per_wrong }
  } catch (e) { /* defaults stay */ }
}
async function saveGrading() {
  savingGrading.value = true
  try {
    const current = await api.get(`/admin/courses/${courseId.value}/grading-config`)
    await api.put(`/admin/courses/${courseId.value}/grading-config`, { ...current, ...grading.value })
    flash('Grading saved.', 'success')
  } catch (e) {
    flash(e.message, 'error')
  } finally {
    savingGrading.value = false
  }
}

// --- data loading ---------------------------------------------------------
async function loadCourses() {
  courses.value = await api.get('/admin/courses')
}
async function loadQuestions() {
  loading.value.questions = true
  try { questions.value = await api.get(`/admin/multichoice/questions?course_id=${courseId.value}`) }
  finally { loading.value.questions = false }
}
async function loadCards() {
  loading.value.cards = true
  try { cards.value = await api.get(`/admin/multichoice/cards?course_id=${courseId.value}`) }
  finally { loading.value.cards = false }
}
async function loadSheets() {
  loading.value.sheets = true
  try { sheets.value = await api.get(`/admin/multichoice/sheets?course_id=${courseId.value}`) }
  finally { loading.value.sheets = false }
}
async function loadStudents() {
  loading.value.students = true
  try { students.value = await api.get(`/admin/students?course_id=${courseId.value}`) }
  finally { loading.value.students = false }
}

function onCourseChange() {
  loadQuestions()
  loadCards()
  loadSheets()
  loadStudents()
  loadGrading()
}

function flash(msg, type) {
  message.value = msg
  msgType.value = type
}

onMounted(async () => {
  try {
    await loadCourses()
    if (courses.value.length === 1) {
      courseId.value = courses.value[0].id
      onCourseChange()
    }
  } catch (e) {
    flash(e.message, 'error')
  }
})
</script>

<style scoped>
.page-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--fc-space-sm); }
.page-title { font-size: var(--fc-fs-md); font-weight: 700; color: var(--fc-ink); }
.section-title { font-size: var(--fc-fs-sm); font-weight: 700; color: var(--fc-ink); }
.hint { font-size: var(--fc-fs-sm); }
.option-row { display: flex; align-items: center; gap: var(--fc-space-xs); }
.q-index { min-width: 18px; }
.row-actions { display: flex; gap: 6px; }
.window-pair { display: flex; align-items: center; gap: var(--fc-space-xs); flex-wrap: wrap; }
.window-pair__picker { width: 210px; }
.window-pair__sep { color: var(--fc-text-soft); }
</style>
