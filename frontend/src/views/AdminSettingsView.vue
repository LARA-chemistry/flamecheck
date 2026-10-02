<template>
  <n-space vertical size="large">
    <n-card title="Application settings" size="small" :bordered="false">
      <n-form label-placement="left" label-width="220">
        <n-form-item label="Points per analysis">
          <n-input-number v-model:value="appSettings.points_per_analysis" :min="0" />
        </n-form-item>
        <n-form-item label="Analyses per course">
          <n-input-number v-model:value="appSettings.analyses_per_course" :min="1" />
        </n-form-item>
        <n-form-item label="Active course">
          <n-select
            v-model:value="appSettings.active_course_id"
            :options="courseOptions"
            clearable
            placeholder="(none)"
            style="width: 320px"
          />
        </n-form-item>
        <n-button type="primary" :loading="savingAppSettings" @click="saveAppSettings">
          Save Application Settings
        </n-button>
      </n-form>
    </n-card>

    <n-card size="small" :bordered="false">
      <div class="grading-card-head">
        <h3 class="grading-card-title">Default grading configuration</h3>
        <span class="grading-card-hint">
          Used by any course that does not have its own settings.
          Override per course in <strong>Courses</strong>.
        </span>
      </div>
      <n-form label-placement="left" label-width="220">
        <n-form-item label="Points per correct ion">
          <n-input-number v-model:value="grading.points_per_correct_ion" :min="0" />
        </n-form-item>
        <n-form-item label="Penalty 2nd submission">
          <n-input-number v-model:value="grading.penalty_second_submission" :min="0" />
        </n-form-item>
        <n-form-item label="Penalty 3rd submission">
          <n-input-number v-model:value="grading.penalty_third_submission" :min="0" />
        </n-form-item>
        <n-form-item label="False positive deduction">
          <n-input-number v-model:value="grading.false_positive_deduction" :min="0" />
        </n-form-item>
        <n-form-item label="Grading mode">
          <n-select
            v-model:value="grading.grading_mode"
            :options="[{ label: 'Per Ion', value: 'per_ion' }, { label: 'Per Analysis', value: 'per_analysis' }]"
          />
        </n-form-item>
        <n-form-item label="Max submissions per analysis">
          <n-input-number v-model:value="grading.max_submissions_per_analysis" :min="1" />
        </n-form-item>
        <n-form-item label="Final score strategy">
          <n-select
            v-model:value="grading.final_score_strategy"
            :options="[{ label: 'Best', value: 'best' }, { label: 'Last', value: 'last' }]"
          />
        </n-form-item>
        <n-button type="primary" :loading="savingGrading" @click="saveGrading">
          Save Grading Configuration
        </n-button>
      </n-form>
    </n-card>

    <!-- Database backup / restore -->
    <n-card size="small" :bordered="false">
      <div class="grading-card-head">
        <h3 class="grading-card-title">Database</h3>
        <span class="grading-card-hint">
          Back up or restore the {{ dbStatus.backend }} database. Scheduled backups run in-process at the
          configured interval (disable here and use ``manage.py backup_database`` from cron if you prefer).
        </span>
      </div>

      <n-alert v-if="!dbStatus.sqlite" type="warning" title="Backend not supported" style="margin-bottom: var(--fc-space-sm)">
        Database backups are only available for the SQLite backend. This deployment uses
        "{{ dbStatus.backend }}"; use its native tooling (e.g. pg_dump) instead.
      </n-alert>

      <template v-if="dbStatus.sqlite">
        <n-form label-placement="left" label-width="220">
          <n-form-item label="Scheduled backup">
            <n-switch v-model:value="appSettings.backup_enabled" />
          </n-form-item>
          <n-form-item label="Interval (minutes)" :disabled="!appSettings.backup_enabled">
            <n-input-number v-model:value="appSettings.backup_interval_minutes" :min="1" :disabled="!appSettings.backup_enabled" />
          </n-form-item>
          <n-form-item label="Backup location" :disabled="!appSettings.backup_enabled">
            <n-input
              v-model:value="appSettings.backup_location"
              placeholder="backups (relative to project root) or /abs/path"
              :disabled="!appSettings.backup_enabled"
              style="width: 380px"
            />
          </n-form-item>
          <n-form-item label="Keep last N" :disabled="!appSettings.backup_enabled">
            <n-input-number v-model:value="appSettings.backup_keep" :min="1" :disabled="!appSettings.backup_enabled" />
          </n-form-item>
          <n-button type="primary" :loading="savingAppSettings" @click="saveAppSettings">
            Save Database Settings
          </n-button>
        </n-form>

        <n-divider style="margin: var(--fc-space-md) 0" />

        <n-space align="center" :wrap="true" style="margin-bottom: var(--fc-space-sm)">
          <n-button type="primary" :loading="backingUp" @click="backupNow">Backup Database</n-button>
          <n-text v-if="dbStatus.last_backup_at" depth="3" class="hint">
            Last backup: {{ formatIso(dbStatus.last_backup_at) }}
            ({{ dbStatus.last_backup_file }})
          </n-text>
          <n-text v-if="dbStatus.last_restore_at" depth="3" class="hint">
            · Last restore: {{ formatIso(dbStatus.last_restore_at) }} ({{ dbStatus.last_restore_file }})
          </n-text>
        </n-space>

        <n-data-table
          v-if="dbStatus.backups.length"
          :columns="backupCols"
          :data="dbStatus.backups"
          size="small"
          :max-height="280"
        />
        <n-empty v-else description="No backups yet — click “Backup Database” to take the first one." />
      </template>
    </n-card>

    <n-alert v-if="message" :type="msgType">{{ message }}</n-alert>
  </n-space>
</template>

<script setup>
import { ref, computed, onMounted, h } from 'vue'
import { api } from '../api/client'
import {
  NSpace, NButton, NInputNumber, NInput, NSelect, NForm, NFormItem, NAlert,
  NCard, NSwitch, NDivider, NDataTable, NEmpty, NText, NPopconfirm,
} from 'naive-ui'

const message = ref('')
const msgType = ref('success')

const courses = ref([])
const appSettings = ref({
  points_per_analysis: 10,
  analyses_per_course: 3,
  active_course_id: null,
  backup_enabled: false,
  backup_interval_minutes: 60,
  backup_location: 'backups',
  backup_keep: 10,
})
const grading = ref({
  points_per_correct_ion: 10,
  penalty_second_submission: 2,
  penalty_third_submission: 4,
  false_positive_deduction: 0,
  grading_mode: 'per_ion',
  max_submissions_per_analysis: 3,
  final_score_strategy: 'best',
})
const savingAppSettings = ref(false)
const savingGrading = ref(false)

// ---- database backups ------------------------------------------------------
const dbStatus = ref({
  backend: 'sqlite',
  sqlite: true,
  enabled: false,
  interval_minutes: 60,
  location: 'backups',
  keep: 10,
  last_backup_at: null,
  last_backup_file: null,
  last_restore_at: null,
  last_restore_file: null,
  backups: [],
})
const backingUp = ref(false)
const restoring = ref(null)

function formatIso(iso) {
  return iso ? new Date(iso).toLocaleString() : ''
}
function formatBytes(n) {
  if (n == null) return ''
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

const backupCols = [
  { title: 'File', key: 'file', ellipsis: { tooltip: true } },
  { title: 'Size', key: 'size', width: 90, render: (r) => formatBytes(r.size) },
  { title: 'Modified', key: 'modified_at', width: 180, render: (r) => formatIso(r.modified_at) },
  {
    title: 'Restore',
    key: 'actions',
    width: 150,
    render: (row) =>
      h(
        NPopconfirm,
        {
          onPositiveClick: () => restoreBackup(row.file),
          positiveText: 'Restore from this backup?',
        },
        { trigger: () => h(NButton, { size: 'tiny', type: 'warning', secondary: true, loading: restoring.value === row.file }, () => 'Restore'),
          default: () => 'This replaces the current database with the selected backup. Continue?',
        },
      ),
  },
]

async function loadDbStatus() {
  try {
    dbStatus.value = await api.get('/admin/database/backups')
  } catch (e) {
    /* ignore */
  }
}

async function backupNow() {
  backingUp.value = true
  try {
    dbStatus.value = await api.post('/admin/database/backup')
    message.value = `Backup created: ${dbStatus.value.last_backup_file}`
    msgType.value = 'success'
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  } finally {
    backingUp.value = false
  }
}

async function restoreBackup(file) {
  restoring.value = file
  try {
    dbStatus.value = await api.post('/admin/database/restore', { file })
    message.value = `Database restored from ${file}. Restart the server for full consistency.`
    msgType.value = 'success'
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  } finally {
    restoring.value = null
  }
}

async function loadCourses() {
  try {
    courses.value = await api.get('/admin/courses')
  } catch (e) {
    /* ignore */
  }
}
async function loadAppSettings() {
  try {
    appSettings.value = await api.get('/admin/app-settings')
  } catch (e) {
    /* ignore */
  }
}
async function loadGrading() {
  try {
    grading.value = await api.get('/admin/grading-config')
  } catch (e) {
    /* ignore */
  }
}

async function saveAppSettings() {
  savingAppSettings.value = true
  try {
    appSettings.value = await api.put('/admin/app-settings', appSettings.value)
    message.value = 'Application settings saved.'
    msgType.value = 'success'
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  } finally {
    savingAppSettings.value = false
  }
}

async function saveGrading() {
  savingGrading.value = true
  try {
    grading.value = await api.put('/admin/grading-config', grading.value)
    message.value = 'Grading config saved.'
    msgType.value = 'success'
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  } finally {
    savingGrading.value = false
  }
}

onMounted(() => {
  loadCourses()
  loadAppSettings()
  loadGrading()
  loadDbStatus()
})
</script>

<style scoped>
.grading-card-head {
  margin-bottom: var(--fc-space-sm);
}
.grading-card-title {
  font-size: var(--fc-fs-md);
  font-weight: 700;
  color: var(--fc-ink);
  margin: 0 0 4px;
}
.grading-card-hint {
  font-size: var(--fc-fs-sm);
  color: var(--fc-text-soft);
}
</style>
