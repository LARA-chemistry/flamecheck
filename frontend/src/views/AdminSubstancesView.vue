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
          <code>wikipedia_link</code>. Separate several ions or synonyms with a
          <strong>semicolon</strong> (e.g. <code>Na+;Cl-</code>) to avoid CSV quoting issues.
          Rows are matched by name - a match updates the existing substance, otherwise a new
          one is created.
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
        <n-button size="small" @click="loadSubstances">Refresh</n-button>
      </div>
      <n-data-table :columns="subCols" :data="substances" size="small" :loading="loading" />
    </n-card>

    <n-alert v-if="message" :type="msgType" closable @close="message = ''">{{ message }}</n-alert>
  </n-space>
</template>

<script setup>
import { ref, onMounted, h } from 'vue'
import { api } from '../api/client'
import {
  NSpace, NButton, NCard, NDataTable, NUpload, NCheckbox, NAlert,
  NTag, NText,
} from 'naive-ui'

const message = ref('')
const msgType = ref('success')
const loading = ref(true)
const substances = ref([])
const result = ref(null)
const uploading = ref(false)
const createMissingIons = ref(false)
const file = ref(null)
const fileList = ref([])

const subCols = [
  { title: 'Name', key: 'name', render: (row) => row.name },
  { title: 'Formula', key: 'formula', render: (row) => row.formula || '-' },
  {
    title: 'Ions',
    key: 'ions',
    render: (row) =>
      row.ions.length
        ? h(NSpace, { size: 'small', wrap: true }, row.ions.map((ion) => h(NTag, { size: 'small', bordered: false, type: 'info' }, () => ion.symbol)))
        : '-',
  },
  { title: 'PubChem', key: 'pubchem_id', render: (row) => row.pubchem_id || '-' },
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

onMounted(() => {
  loadSubstances()
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
