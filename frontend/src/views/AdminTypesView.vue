<template>
  <n-space vertical size="large">
    <n-card size="small" :bordered="false">
      <div class="page-head">
        <h2 class="page-title">Analysis Types</h2>
        <n-button type="primary" size="small" @click="openCreate">+ New Type</n-button>
      </div>
      <n-data-table
        :columns="typeCols"
        :data="types"
        size="small"
        :loading="loading"
        :row-key="(row) => row.id"
        :row-props="(row) => ({ style: 'cursor: pointer', onClick: (e) => onRowClick(row, e) })"
      />
      <n-text depth="3" style="font-size: 12px">Click a row to edit the type.</n-text>
    </n-card>

    <n-modal v-model:show="modal.show" preset="card" :title="modal.editing ? 'Edit Analysis Type' : 'New Analysis Type'" style="width: 600px; max-width: 94vw">
      <n-form label-placement="left" label-width="120">
        <n-form-item label="Name">
          <n-input v-model:value="modal.form.name" placeholder="e.g. Analysis 3 – Cations I+II & anions" />
        </n-form-item>
        <n-form-item label="Description">
          <n-input v-model:value="modal.form.description" type="textarea" :rows="2" placeholder="Short description shown to students" />
        </n-form-item>
        <n-form-item label="Possible ions">
          <n-select
            v-model:value="modal.form.ion_ids"
            :options="ionOptions"
            multiple
            filterable
            placeholder="Select the ions that can occur"
            :loading="loadingIons"
          />
        </n-form-item>
        <n-form-item label="Default window">
          <div class="window-pair">
            <n-date-picker
              v-model:formatted-value="modal.form.default_window_start"
              type="datetime"
              value-format="yyyy-MM-dd HH:mm"
              format="yyyy-MM-dd HH:mm"
              placeholder="Opens"
              class="window-pair__picker"
            />
            <span class="window-pair__sep">→</span>
            <n-date-picker
              v-model:formatted-value="modal.form.default_window_end"
              type="datetime"
              value-format="yyyy-MM-dd HH:mm"
              format="yyyy-MM-dd HH:mm"
              placeholder="Closes"
              class="window-pair__picker"
            />
          </div>
        </n-form-item>
        <n-text depth="3" style="font-size: 12px">
          New sessions (announcements) of this type inherit this window unless overridden per session.
        </n-text>
        <n-form-item label="Max re-trials">
          <n-input-number v-model:value="modal.form.max_repetitions" :min="0" :max="20" />
          <template #feedback>
            "New analysis" mode: re-trial analyses a student may get per announcement after a wrong submission.
          </template>
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button v-if="modal.editing" type="error" ghost @click="removeType">Delete</n-button>
          <n-button @click="modal.show = false">Cancel</n-button>
          <n-button type="primary" :loading="modal.saving" @click="saveType">Save</n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- Per-type sessions (concrete analyses) and their windows -->
    <n-modal v-model:show="sessions.show" preset="card" :title="`Sessions — ${sessions.typeName}`" style="width: 760px; max-width: 96vw">
      <n-space vertical>
        <n-text depth="3" style="font-size: 13px">
          Each session (announcement) has its own submission window. Use the pickers to set or
          adjust a session's window, or add a new session that inherits the type's default window.
        </n-text>
        <n-data-table :columns="sessionCols" :data="sessions.rows" size="small" :loading="sessions.loading" />
        <n-empty v-if="!sessions.loading && sessions.rows.length === 0" description="No sessions for this type yet." size="small" />

        <!-- New session row -->
        <div class="new-session">
          <n-text strong style="font-size: 13px">New session</n-text>
          <n-space align="center" :wrap="true">
            <n-input-number v-model:value="sessions.new.number" :min="1" size="small" style="width: 110px" placeholder="Announcement #" />
            <n-select
              v-model:value="sessions.new.courseId"
              :options="courseOptions"
              placeholder="Course"
              size="small"
              style="width: 240px"
              clearable
            />
            <n-date-picker
              v-model:formatted-value="sessions.new.window_start"
              type="datetime"
              value-format="yyyy-MM-dd HH:mm"
              format="yyyy-MM-dd HH:mm"
              placeholder="Opens"
              size="small"
              style="width: 180px"
            />
            <n-date-picker
              v-model:formatted-value="sessions.new.window_end"
              type="datetime"
              value-format="yyyy-MM-dd HH:mm"
              format="yyyy-MM-dd HH:mm"
              placeholder="Closes"
              size="small"
              style="width: 180px"
            />
            <n-button type="primary" size="small" :loading="sessions.new.saving" @click="createSession">Add session</n-button>
          </n-space>
        </div>
      </n-space>
    </n-modal>

    <n-alert v-if="message" :type="msgType">{{ message }}</n-alert>
  </n-space>
</template>

<script setup>
import { ref, computed, onMounted, h } from 'vue'
import { api } from '../api/client'
import {
  NSpace, NButton, NInput, NInputNumber, NSelect, NDataTable, NCard, NForm, NFormItem,
  NModal, NAlert, NEmpty, NText, NDatePicker,
} from 'naive-ui'
import IonSymbol from '../components/IonSymbol.vue'

const message = ref('')
const msgType = ref('success')
const loading = ref(true)
const types = ref([])
const ions = ref([])
const loadingIons = ref(false)
const courses = ref([])

const courseOptions = computed(() => courses.value.map((c) => ({ label: c.name, value: c.id })))

const modal = ref({
  show: false,
  editing: false,
  saving: false,
  form: { id: null, name: '', description: '', ion_ids: [], default_window_start: null, default_window_end: null, max_repetitions: 2 },
})

// Per-type sessions (concrete analyses) + their windows.
const sessions = ref({
  show: false,
  loading: false,
  typeId: null,
  typeName: '',
  defaultStart: null,
  defaultEnd: null,
  rows: [],
  new: { number: 1, courseId: null, window_start: null, window_end: null, saving: false },
})

const ionOptions = ref([])

// Format an ISO datetime to the picker's "yyyy-MM-dd HH:mm" shape (local time).
function isoToPicker(iso) {
  if (!iso) return null
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return null
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}
// Convert a picker value (formatted string or ms timestamp) to an ISO string
// for the API.
function timestampToIso(v) {
  if (v == null) return null
  const d = new Date(typeof v === 'string' ? v.replace(' ', 'T') : v)
  return Number.isNaN(d.getTime()) ? null : d.toISOString()
}

const typeCols = [
  { title: 'Name', key: 'name', render: (row) => row.name },
  { title: 'Description', key: 'description', ellipsis: { tooltip: true } },
  { title: 'Ions', key: 'ions', render: (row) => `${row.ions.length}` },
  { title: 'Max re-trials', key: 'max_repetitions', render: (row) => `${row.max_repetitions ?? 2}` },
  {
    title: 'Default window',
    key: 'default_window',
    render: (row) =>
      row.default_window_start
        ? `${isoToPicker(row.default_window_start)} → ${isoToPicker(row.default_window_end)}`
        : h(NText, { depth: 3 }, () => '—'),
  },
  { title: 'Sessions', key: 'session_count', render: (row) => `${row.session_count ?? 0}` },
  {
    title: 'Actions',
    key: 'actions',
    render: (row) =>
      h('div', { style: 'display:flex;gap:6px;flex-wrap:wrap' }, [
        h(NButton, { size: 'tiny', type: 'primary', secondary: true, onClick: () => openEdit(row) }, () => 'Edit'),
        h(NButton, { size: 'tiny', secondary: true, onClick: () => openSessions(row) }, () => 'Windows'),
      ]),
  },
]

const sessionCols = [
  { title: '#', key: 'number', width: 40, render: (row) => `#${row.number}` },
  { title: 'Course', key: 'course', render: (row) => row.course || '—' },
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
        'onUpdate:formattedValue': (v) => updateSessionWindow(row, 'window_start', v),
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
        'onUpdate:formattedValue': (v) => updateSessionWindow(row, 'window_end', v),
      }),
  },
]

async function loadTypes() {
  loading.value = true
  try {
    types.value = await api.get('/admin/analysis-types')
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  } finally {
    loading.value = false
  }
}

async function loadCourses() {
  try {
    courses.value = await api.get('/admin/courses')
  } catch (e) {
    /* ignore */
  }
}

async function loadIons() {
  loadingIons.value = true
  try {
    ions.value = await api.get('/ions')
    ionOptions.value = ions.value.map((i) => ({
      label: h('span', [h(IonSymbol, { symbol: i.symbol }), ` (${i.name})`]),
      value: i.id,
    }))
  } catch (e) {
    /* ignore */
  } finally {
    loadingIons.value = false
  }
}

// Open the edit modal for a row, but ignore clicks on the row's action buttons.
function onRowClick(row, event) {
  if (event && event.target.closest('button, a')) return
  openEdit(row)
}

function openCreate() {
  modal.value = {
    show: true,
    editing: false,
    saving: false,
    form: { id: null, name: '', description: '', ion_ids: [], default_window_start: null, default_window_end: null, max_repetitions: 2 },
  }
}

function openEdit(row) {
  modal.value = {
    show: true,
    editing: true,
    saving: false,
    form: {
      id: row.id,
      name: row.name,
      description: row.description || '',
      ion_ids: row.ions.map((i) => i.id),
      default_window_start: isoToPicker(row.default_window_start),
      default_window_end: isoToPicker(row.default_window_end),
      max_repetitions: row.max_repetitions ?? 2,
    },
  }
}

async function saveType() {
  const f = modal.value.form
  if (!f.name) {
    message.value = 'Name is required.'
    msgType.value = 'error'
    return
  }
  if (f.default_window_start && f.default_window_end && timestampToIso(f.default_window_start) >= timestampToIso(f.default_window_end)) {
    message.value = 'The window must close after it opens.'
    msgType.value = 'error'
    return
  }
  modal.value.saving = true
  try {
    const payload = {
      name: f.name,
      description: f.description,
      ion_ids: f.ion_ids,
      default_window_start: timestampToIso(f.default_window_start),
      default_window_end: timestampToIso(f.default_window_end),
      max_repetitions: f.max_repetitions ?? 2,
    }
    if (modal.value.editing) {
      await api.put(`/admin/analysis-types/${f.id}`, payload)
      message.value = 'Analysis type updated.'
    } else {
      await api.post('/admin/analysis-types', payload)
      message.value = 'Analysis type created.'
    }
    msgType.value = 'success'
    modal.value.show = false
    await loadTypes()
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  } finally {
    modal.value.saving = false
  }
}

async function removeType() {
  const f = modal.value.form
  if (!confirm(`Delete analysis type "${f.name}"?`)) return
  try {
    await api.delete(`/admin/analysis-types/${f.id}`)
    message.value = 'Analysis type deleted.'
    msgType.value = 'success'
    modal.value.show = false
    await loadTypes()
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  }
}

// ---- per-type sessions (windows) ------------------------------------------
async function openSessions(row) {
  sessions.value.show = true
  sessions.value.typeId = row.id
  sessions.value.typeName = row.name
  sessions.value.defaultStart = row.default_window_start
  sessions.value.defaultEnd = row.default_window_end
  sessions.value.rows = []
  sessions.value.loading = true
  sessions.value.new = { number: 1, courseId: null, window_start: isoToPicker(row.default_window_start), window_end: isoToPicker(row.default_window_end), saving: false }
  try {
    const list = await api.get(`/admin/analysis-instances?type_id=${row.id}`)
    sessions.value.rows = list.map((i) => ({ ...i }))
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  } finally {
    sessions.value.loading = false
  }
}

async function updateSessionWindow(row, field, value) {
  // value is the picker's formatted string ("yyyy-MM-dd HH:mm") or null.
  row[field] = value ? timestampToIso(value) : null
  try {
    await api.put(`/admin/analysis-instances/${row.id}`, {
      window_start: row.window_start,
      window_end: row.window_end,
    })
    message.value = 'Window saved.'
    msgType.value = 'success'
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  }
}

async function createSession() {
  const s = sessions.value
  const start = s.new.window_start
  const end = s.new.window_end
  if (!start || !end) {
    message.value = 'Set both window times for the new session.'
    msgType.value = 'error'
    return
  }
  if (new Date(start.replace(' ', 'T')) >= new Date(end.replace(' ', 'T'))) {
    message.value = 'The session window must close after it opens.'
    msgType.value = 'error'
    return
  }
  s.new.saving = true
  try {
    await api.post('/admin/analysis-instances', {
      type_id: s.typeId,
      course_id: s.new.courseId || null,
      number: s.new.number,
      window_start: timestampToIso(start),
      window_end: timestampToIso(end),
    })
    message.value = `Session #${s.new.number} added.`
    msgType.value = 'success'
    await openSessions({ id: s.typeId, name: s.typeName, default_window_start: s.defaultStart, default_window_end: s.defaultEnd })
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  } finally {
    s.new.saving = false
  }
}

onMounted(() => {
  loadTypes()
  loadIons()
  loadCourses()
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
.new-session {
  padding-top: var(--fc-space-xs);
  border-top: 1px solid var(--fc-border);
  display: flex;
  flex-direction: column;
  gap: var(--fc-space-xs);
}
</style>
