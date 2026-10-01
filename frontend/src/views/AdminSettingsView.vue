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

    <n-alert v-if="message" :type="msgType">{{ message }}</n-alert>
  </n-space>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '../api/client'
import {
  NSpace, NButton, NInputNumber, NSelect, NForm, NFormItem, NAlert, NCard,
} from 'naive-ui'

const message = ref('')
const msgType = ref('success')

const courses = ref([])
const appSettings = ref({
  points_per_analysis: 10,
  analyses_per_course: 3,
  active_course_id: null,
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

const courseOptions = computed(() =>
  courses.value.map((c) => ({ label: c.name, value: c.id })),
)

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
