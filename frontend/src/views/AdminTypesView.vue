<template>
  <n-space vertical size="large">
    <n-card size="small" :bordered="false">
      <div class="page-head">
        <h2 class="page-title">Analysis Types</h2>
        <n-button type="primary" size="small" @click="openCreate">+ New Type</n-button>
      </div>
      <n-data-table :columns="typeCols" :data="types" size="small" :loading="loading" />
    </n-card>

    <n-modal v-model:show="modal.show" preset="card" :title="modal.editing ? 'Edit Analysis Type' : 'New Analysis Type'" style="width: 560px; max-width: 94vw">
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
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button v-if="modal.editing" type="error" ghost @click="removeType">Delete</n-button>
          <n-button @click="modal.show = false">Cancel</n-button>
          <n-button type="primary" :loading="modal.saving" @click="saveType">Save</n-button>
        </n-space>
      </template>
    </n-modal>

    <n-alert v-if="message" :type="msgType">{{ message }}</n-alert>
  </n-space>
</template>

<script setup>
import { ref, onMounted, h } from 'vue'
import { api } from '../api/client'
import {
  NSpace, NButton, NInput, NSelect, NDataTable, NCard, NForm,
  NFormItem, NModal, NAlert,
} from 'naive-ui'

const message = ref('')
const msgType = ref('success')
const loading = ref(true)
const types = ref([])
const ions = ref([])
const loadingIons = ref(false)

const modal = ref({
  show: false,
  editing: false,
  saving: false,
  form: { id: null, name: '', description: '', ion_ids: [] },
})

const ionOptions = ref([])

const typeCols = [
  { title: 'Name', key: 'name', render: (row) => row.name },
  { title: 'Description', key: 'description', ellipsis: { tooltip: true } },
  { title: 'Possible ions', key: 'ions', render: (row) => `${row.ions.length}` },
  {
    title: 'Actions',
    key: 'actions',
    render: (row) =>
      h('div', { style: 'display:flex;gap:6px' }, [
        h(NButton, { size: 'tiny', type: 'primary', secondary: true, onClick: () => openEdit(row) }, () => 'Edit'),
      ]),
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

async function loadIons() {
  loadingIons.value = true
  try {
    ions.value = await api.get('/ions')
    ionOptions.value = ions.value.map((i) => ({
      label: `${i.symbol} (${i.name})`,
      value: i.id,
    }))
  } catch (e) {
    /* ignore */
  } finally {
    loadingIons.value = false
  }
}

function openCreate() {
  modal.value = { show: true, editing: false, saving: false, form: { id: null, name: '', description: '', ion_ids: [] } }
}

function openEdit(row) {
  modal.value = {
    show: true,
    editing: true,
    saving: false,
    form: { id: row.id, name: row.name, description: row.description || '', ion_ids: row.ions.map((i) => i.id) },
  }
}

async function saveType() {
  const f = modal.value.form
  if (!f.name) {
    message.value = 'Name is required.'
    msgType.value = 'error'
    return
  }
  modal.value.saving = true
  try {
    const payload = { name: f.name, description: f.description, ion_ids: f.ion_ids }
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

onMounted(() => {
  loadTypes()
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
</style>
