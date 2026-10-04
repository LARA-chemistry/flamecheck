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

    <!-- Onboarding: how new student accounts are created (mutually exclusive) -->
    <n-card title="Onboarding" size="small" :bordered="false">
      <n-space vertical size="large">
        <n-text depth="3">
          Choose how new student accounts are created. Exactly one mode is active at a time.
        </n-text>
        <n-radio-group v-model:value="appSettings.onboarding" name="onboarding">
          <n-space vertical>
            <n-space v-for="opt in onboardingOptions" :key="opt.value" vertical size="small">
              <n-radio-button :value="opt.value" :bordered="false" style="width: 240px">
                {{ opt.label }}
              </n-radio-button>
              <n-text depth="3" style="padding-left: 8px">{{ opt.hint }}</n-text>
            </n-space>
          </n-space>
        </n-radio-group>
        <n-button type="primary" :loading="savingAppSettings" @click="saveAppSettings">
          Save Onboarding
        </n-button>
      </n-space>
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
        <n-form-item label="Submission mode">
          <n-select
            v-model:value="grading.submission_mode"
            :options="[
              { label: 'Resubmit (default)', value: 'resubmit' },
              { label: 'New analysis on wrong submission', value: 'new_analysis' },
            ]"
          />
        </n-form-item>
        <n-form-item label="Retry point deduction">
          <n-input-number v-model:value="grading.retry_point_deduction" :min="0" />
          <template #feedback>Points subtracted per earlier re-trial (new-analysis mode only).</template>
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

    <!-- Login-page branding (university logo + login QR code) -->
    <n-card size="small" :bordered="false">
      <div class="grading-card-head">
        <h3 class="grading-card-title">Login</h3>
        <span class="grading-card-hint">
          Branding shown on the public login page. The logo appears in the upper-right
          corner (SVG or PNG); the QR code — a scan of the login URL — appears below the
          login card on wide screens (SVG or PNG) so a smartphone can be used to log in.
        </span>
      </div>

      <n-space vertical size="large">
        <!-- University / institut logo -->
        <n-space align="center" :wrap="true">
          <div class="branding-slot">
            <img v-if="branding.login_logo" :src="branding.login_logo" alt="Login logo preview" class="branding-preview branding-preview--logo" />
            <div v-else class="branding-placeholder branding-placeholder--logo">
              <span>No logo</span>
            </div>
          </div>
          <div class="branding-controls">
            <p class="branding-label">University / institut logo <span class="branding-sub">(SVG or PNG)</span></p>
            <n-space align="center">
              <n-button type="primary" secondary :loading="brandingBusy === 'logo'" @click="pickFile('logo')">
                Upload logo
              </n-button>
              <n-button
                v-if="branding.login_logo"
                type="warning"
                secondary
                :loading="brandingBusy === 'remove-logo'"
                @click="removeBranding('logo')"
              >
                Remove
              </n-button>
            </n-space>
          </div>
        </n-space>

        <n-divider style="margin: 0" />

        <!-- Login QR code -->
        <n-space align="center" :wrap="true">
          <div class="branding-slot">
            <img v-if="branding.login_qr" :src="branding.login_qr" alt="Login QR preview" class="branding-preview branding-preview--qr" />
            <div v-else class="branding-placeholder branding-placeholder--qr">
              <span>No QR code</span>
            </div>
          </div>
          <div class="branding-controls">
            <p class="branding-label">Login QR code <span class="branding-sub">(SVG or PNG)</span></p>
            <n-space align="center">
              <n-button type="primary" secondary :loading="brandingBusy === 'qr'" @click="pickFile('qr')">
                Upload QR code
              </n-button>
              <n-button
                v-if="branding.login_qr"
                type="warning"
                secondary
                :loading="brandingBusy === 'remove-qr'"
                @click="removeBranding('qr')"
              >
                Remove
              </n-button>
            </n-space>
          </div>
        </n-space>
      </n-space>

      <!-- Hidden file inputs (one per target) -->
      <input
        ref="logoInput"
        type="file"
        accept=".svg,.png,image/svg+xml,image/png"
        style="display: none"
        @change="onFileChosen('logo', $event)"
      />
      <input
        ref="qrInput"
        type="file"
        accept=".svg,.png,image/svg+xml,image/png"
        style="display: none"
        @change="onFileChosen('qr', $event)"
      />
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
  NRadioGroup, NRadioButton,
} from 'naive-ui'

const message = ref('')
const msgType = ref('success')

// ---- login-page branding ---------------------------------------------------
const branding = ref({ login_logo: null, login_qr: null })
const brandingBusy = ref(null) // 'logo' | 'qr' | 'remove-logo' | 'remove-qr' | null
const logoInput = ref(null)
const qrInput = ref(null)

const courses = ref([])
const appSettings = ref({
  points_per_analysis: 10,
  analyses_per_course: 3,
  active_course_id: null,
  onboarding: 'manual',
  backup_enabled: false,
  backup_interval_minutes: 60,
  backup_location: 'backups',
  backup_keep: 10,
})

// Descriptions for the mutually-exclusive onboarding modes (the radio group).
const onboardingOptions = [
  { value: 'manual', label: 'Manual', hint: 'A new student account is created by an admin in Admin → Courses → Members.' },
  { value: 'self_registration', label: 'Self-registration', hint: 'The login page shows a “Register” link. Students register and confirm their e-mail address (console e-mail in development).' },
  { value: 'oauth', label: 'OAuth', hint: 'Students sign in via an external identity provider (django-allauth); a student account is created and they complete an onboarding page (course + details + generated analyses).' },
]
const grading = ref({
  points_per_correct_ion: 10,
  penalty_second_submission: 2,
  penalty_third_submission: 4,
  false_positive_deduction: 0,
  grading_mode: 'per_ion',
  max_submissions_per_analysis: 3,
  final_score_strategy: 'best',
  submission_mode: 'resubmit',
  retry_point_deduction: 0,
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

async function loadBranding() {
  try {
    branding.value = await api.get('/branding')
  } catch (e) {
    /* ignore */
  }
}

function pickFile(kind) {
  const input = kind === 'logo' ? logoInput.value : qrInput.value
  input && input.click()
}

async function onFileChosen(kind, event) {
  const input = event.target
  const file = input.files && input.files[0]
  input.value = '' // allow re-selecting the same file
  if (!file) return
  brandingBusy.value = kind
  try {
    const path = kind === 'logo' ? '/admin/branding/logo' : '/admin/branding/qr'
    const res = await api.upload(path, file)
    branding.value = { ...branding.value, [kind]: res[kind] }
    message.value = `${kind === 'logo' ? 'Logo' : 'QR code'} uploaded.`
    msgType.value = 'success'
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  } finally {
    brandingBusy.value = null
  }
}

async function removeBranding(kind) {
  brandingBusy.value = `remove-${kind}`
  try {
    const path = kind === 'logo' ? '/admin/branding/logo' : '/admin/branding/qr'
    await api.delete(path)
    branding.value = { ...branding.value, [kind]: null }
    message.value = `${kind === 'logo' ? 'Logo' : 'QR code'} removed.`
    msgType.value = 'success'
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  } finally {
    brandingBusy.value = null
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
  loadBranding()
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

/* ---- login-page branding ------------------------------------------------- */
.branding-slot {
  width: 120px;
  height: 96px;
  flex-shrink: 0;
  display: grid;
  place-items: center;
  border: 1px dashed var(--fc-border);
  border-radius: var(--fc-radius-sm);
  background: var(--fc-bg);
  overflow: hidden;
}
.branding-preview {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}
.branding-preview--logo {
  width: 100%;
  height: auto;
}
.branding-preview--qr {
  width: 84px;
  height: 84px;
}
.branding-placeholder {
  display: grid;
  place-items: center;
  width: 100%;
  height: 100%;
  color: var(--fc-muted);
  font-size: var(--fc-fs-xs);
  font-weight: 600;
}
.branding-controls {
  display: flex;
  flex-direction: column;
  gap: var(--fc-space-xs);
  min-width: 0;
}
.branding-label {
  margin: 0;
  font-size: var(--fc-fs-base);
  font-weight: 700;
  color: var(--fc-ink);
}
.branding-sub {
  font-weight: 500;
  font-size: var(--fc-fs-xs);
  color: var(--fc-muted);
}
</style>
