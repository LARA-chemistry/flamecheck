<template>
  <n-space vertical size="large">
    <!-- CSV import -->
    <n-card size="small" :bordered="false">
      <div class="page-head">
        <h2 class="page-title">Import substances (CSV)</h2>
        <n-button size="small" secondary @click="downloadTemplate">Download template</n-button>
      </div>
      <n-space vertical size="small">
        <n-text depth="3" class="hint">
          Upload a CSV with the columns: <code>name</code> (required), <code>synonyms</code>,
          <code>formula</code>, <code>ions</code>, <code>pubchem_id</code>,
          <code>wikipedia_link</code>. Columns are separated by
          <code>;</code> and several ions or synonyms are separated by
          <code>,</code> (e.g. <code>Na+1,Cl-1</code>), so a cell may hold commas
          without quoting. Rows are matched by name - a match updates the existing
          substance, otherwise a new one is created.
        </n-text>
        <n-space align="center" :wrap="true">
          <n-upload
            :file-list="fileList"
            :max="1"
            accept=".csv,text/csv"
            @update:file-list="onFileChange"
          >
            <n-button size="small" :disabled="!file">Choose CSV file</n-button>
          </n-upload>
          <n-checkbox v-model:checked="createMissingIons">Create missing ions</n-checkbox>
          <n-button type="primary" size="small" :loading="uploading" :disabled="!file" @click="doUpload">
            Upload &amp; import
          </n-button>
        </n-space>
        <n-alert v-if="result" :type="result.errors.length ? 'warning' : 'success'" title="Import result" closable @close="result = null">
          <n-space vertical size="small">
            <n-text>
              {{ result.created }} created, {{ result.updated }} updated, {{ result.skipped }} skipped
              ({{ result.total_rows }} rows).
            </n-text>
            <template v-if="result.missing_ions.length">
              <n-text depth="3">Unmatched ion symbols (not imported):</n-text>
              <n-space :wrap="true" size="small">
                <n-tag v-for="s in result.missing_ions" :key="s" size="small" type="warning" :bordered="false">{{ s }}</n-tag>
              </n-space>
            </template>
            <template v-if="result.errors.length">
              <n-text depth="3">Issues:</n-text>
              <ul class="err-list">
                <li v-for="(e, i) in result.errors" :key="i">{{ e }}</li>
              </ul>
            </template>
          </n-space>
        </n-alert>
      </n-space>
    </n-card>

    <!-- Substance catalog -->
    <n-card size="small" :bordered="false">
      <div class="page-head">
        <h2 class="page-title">Substances</h2>
        <n-space size="small">
          <n-button size="small" @click="loadSubstances">Refresh</n-button>
          <n-button size="small" secondary :disabled="!substances.length" @click="doExport">
            Export to CSV
          </n-button>
        </n-space>
      </div>
      <n-data-table
        :columns="subCols"
        :data="substances"
        size="small"
        :loading="loading"
        :row-key="(row) => row.id"
        :row-props="(row) => ({ style: 'cursor: pointer', onClick: (e) => onRowClick(row, e) })"
      />
      <n-text depth="3" style="font-size: 12px">Click a row to edit the substance.</n-text>
    </n-card>

    <!-- Edit substance (opened by clicking a table row) -->
    <n-modal v-model:show="modal.show" preset="card" title="Edit substance" style="width: 620px; max-width: 94vw">
      <n-form label-placement="left" label-width="110">
        <n-form-item label="Name">
          <n-input v-model:value="modal.form.name" placeholder="e.g. Sodium chloride" />
        </n-form-item>
        <n-form-item label="Synonyms">
          <n-select v-model:value="modal.form.synonyms" multiple tag :options="[]" placeholder="Type a synonym and press Enter" />
        </n-form-item>
        <n-form-item label="Formula">
          <n-input v-model:value="modal.form.formula" placeholder="e.g. NaCl" />
        </n-form-item>
        <n-form-item label="Ions">
          <n-select
            v-model:value="modal.form.ion_ids"
            :options="ionOptions"
            :render-label="renderIonLabel"
            multiple
            filterable
            :loading="loadingIons"
            placeholder="Select the ions contained in this substance"
          />
        </n-form-item>
        <n-form-item label="PubChem ID">
          <n-input v-model:value="modal.form.pubchem_id" placeholder="e.g. 5234" />
        </n-form-item>
        <n-form-item label="Wikipedia">
          <n-input v-model:value="modal.form.wikipedia_link" placeholder="https://en.wikipedia.org/wiki/Sodium_chloride" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="modal.show = false">Cancel</n-button>
          <n-button type="primary" :loading="modal.saving" @click="saveSubstance">Save</n-button>
        </n-space>
      </template>
    </n-modal>

    <n-alert v-if="message" :type="msgType" closable @close="message = ''">{{ message }}</n-alert>
  </n-space>
</template>

<script setup>
import { ref, onMounted, h } from 'vue'
import { api } from '../api/client'
import {
  NSpace, NButton, NCard, NDataTable, NUpload, NCheckbox, NAlert,
  NTag, NText, NModal, NForm, NFormItem, NInput, NSelect,
} from 'naive-ui'
import IonSymbol from '../components/IonSymbol.vue'

const message = ref('')
const msgType = ref('success')
const loading = ref(true)
const substances = ref([])
const result = ref(null)
const uploading = ref(false)
const createMissingIons = ref(false)
const file = ref(null)
const fileList = ref([])

// Ion options for the edit modal (loaded from the ion catalog).
const ions = ref([])
const loadingIons = ref(false)
const ionOptions = ref([])

// Edit modal (opened by clicking a table row).
const modal = ref({
  show: false,
  saving: false,
  form: { id: null, name: '', synonyms: [], formula: '', ion_ids: [], pubchem_id: '', wikipedia_link: '' },
})

// External reference links (PubChem / Wikipedia) render as real hyperlinks that
// open in a new tab; a dash is shown when the substance has no such reference.
function extLink(label, href) {
  if (!href) return '-'
  return h('a', { href, target: '_blank', rel: 'noopener noreferrer' }, label)
}

const subCols = [
  { title: 'Name', key: 'name', render: (row) => row.name },
  { title: 'Formula', key: 'formula', render: (row) => row.formula || '-' },
  {
    title: 'Ions',
    key: 'ions',
    render: (row) =>
      row.ions.length
        ? h(NSpace, { size: 'small', wrap: true }, row.ions.map((ion) => h(NTag, { size: 'small', bordered: false, type: 'info' }, () => h(IonSymbol, { symbol: ion.symbol }))))
        : '-',
  },
  {
    title: 'PubChem',
    key: 'pubchem_id',
    render: (row) => extLink(row.pubchem_id || 'PubChem', row.pubchem_url),
  },
  {
    title: 'Wikipedia',
    key: 'wikipedia_link',
    render: (row) => extLink('Wikipedia', row.wikipedia_link),
  },
]

function onFileChange(list) {
  fileList.value = list
  file.value = list.length ? list[0].file : null
}

function downloadTemplate() {
  api
    .download('/substances/import-template', 'substances_import_template.csv')
    .catch((e) => {
      message.value = e.message
      msgType.value = 'error'
    })
}

// Download the full catalog as a ";"-separated CSV in the import format, so the
// file can be edited and re-imported directly.
function doExport() {
  api
    .download('/substances/export-csv', 'substances.csv')
    .catch((e) => {
      message.value = e.message
      msgType.value = 'error'
    })
}

async function doUpload() {
  if (!file.value) return
  uploading.value = true
  result.value = null
  try {
    result.value = await api.upload('/substances/import-csv', file.value, {
      create_missing_ions: createMissingIons.value,
    })
    message.value = `Imported: ${result.value.created} created, ${result.value.updated} updated.`
    msgType.value = 'success'
    file.value = null
    fileList.value = []
    await loadSubstances()
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  } finally {
    uploading.value = false
  }
}

async function loadSubstances() {
  loading.value = true
  try {
    substances.value = await api.get('/substances')
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  } finally {
    loading.value = false
  }
}

async function loadIons() {
  loadingIons.value = true
  try {
    ions.value = await api.get('/ions')
    // The label stays a plain string so that filterable search matches on the
    // name; the rich symbol rendering is provided by renderIonLabel below.
    ionOptions.value = ions.value.map((i) => ({ label: `${i.symbol} (${i.name})`, value: i.id }))
  } catch (e) {
    /* ignore - the edit modal simply has no ion options then */
  } finally {
    loadingIons.value = false
  }
}

// Render an ion option's label with the IUPAC-formatted symbol (sub/superscripts).
// A function is required (not a static VNode): naive-ui renders the label in
// several places (tags and dropdown rows), and one VNode instance can only be
// mounted once — a shared instance renders blank.
function renderIonLabel(option) {
  const ion = ions.value.find((i) => i.id === option.value)
  if (!ion) return option.label
  return h('span', [h(IonSymbol, { symbol: ion.symbol }), ` (${ion.name})`])
}

// Open the edit modal for a row, but ignore clicks on cell links/buttons.
function onRowClick(row, event) {
  if (event && event.target.closest('a, button')) return
  openEdit(row)
}

function openEdit(row) {
  modal.value = {
    show: true,
    saving: false,
    form: {
      id: row.id,
      name: row.name,
      synonyms: row.synonyms || [],
      formula: row.formula || '',
      ion_ids: row.ions.map((i) => i.id),
      pubchem_id: row.pubchem_id || '',
      wikipedia_link: row.wikipedia_link || '',
    },
  }
}

async function saveSubstance() {
  const f = modal.value.form
  if (!f.name) {
    message.value = 'Name is required.'
    msgType.value = 'error'
    return
  }
  modal.value.saving = true
  try {
    await api.put(`/substances/${f.id}`, {
      name: f.name,
      synonyms: f.synonyms,
      formula: f.formula,
      ion_ids: f.ion_ids,
      pubchem_id: f.pubchem_id,
      wikipedia_link: f.wikipedia_link,
    })
    message.value = 'Substance updated.'
    msgType.value = 'success'
    modal.value.show = false
    await loadSubstances()
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  } finally {
    modal.value.saving = false
  }
}

onMounted(() => {
  loadSubstances()
  loadIons()
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
.hint code {
  background: rgba(127, 127, 127, 0.14);
  padding: 0 4px;
  border-radius: 3px;
}
.err-list {
  margin: 4px 0 0 18px;
  font-size: var(--fc-fs-sm);
}
</style>
