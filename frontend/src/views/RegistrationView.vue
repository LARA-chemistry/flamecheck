<template>
  <div class="registration-container">
    <n-card class="registration-card" size="small">
      <div class="registration-head">
        <h1 class="registration-title">Welcome, {{ auth.user?.full_name || auth.user?.username }}</h1>
        <p class="registration-sub">
          Almost there. Choose your course and add any details your sign-in provider
          did not supply. Your analyses for the course are generated for you.
        </p>
      </div>

      <n-form ref="formRef" :model="form" :rules="rules" label-placement="left" label-width="160">
        <n-form-item label="Course" path="course_id">
          <n-select
            v-model:value="form.course_id"
            :options="courseOptions"
            :loading="loadingCourses"
            filterable
            clearable
            placeholder="Select your course"
            style="width: 100%"
          />
        </n-form-item>
        <n-form-item label="First name">
          <n-input v-model:value="form.first_name" placeholder="First name" />
        </n-form-item>
        <n-form-item label="Last name">
          <n-input v-model:value="form.last_name" placeholder="Last name" />
        </n-form-item>
        <n-form-item label="Matriculation no.">
          <n-input v-model:value="form.matriculation_no" placeholder="e.g. M123456" />
        </n-form-item>
        <n-form-item label="Labspace ID">
          <n-input v-model:value="form.labspace_id" placeholder="Leave blank to generate one" />
        </n-form-item>
        <n-form-item label="Lab">
          <n-input v-model:value="form.lab" placeholder="e.g. Inorganic Chemistry, Biology track" />
        </n-form-item>
        <n-form-item label="Telephone">
          <n-input v-model:value="form.telephone" placeholder="e.g. +49 151 2345678" />
        </n-form-item>
        <n-form-item label=" ">
          <n-button type="primary" :loading="saving" @click="handleComplete">
            Finish registration
          </n-button>
        </n-form-item>
      </n-form>

      <n-alert v-if="error" type="error" class="registration-error">{{ error }}</n-alert>
    </n-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { api } from '../api/client'
import { NCard, NForm, NFormItem, NInput, NSelect, NButton, NAlert } from 'naive-ui'

const router = useRouter()
const auth = useAuthStore()

const courses = ref([])
const loadingCourses = ref(false)
const saving = ref(false)
const error = ref('')

// Pre-fill with what the sign-in provider already supplied (if any).
const u = auth.user || {}
const form = ref({
  course_id: null,
  first_name: u.first_name || '',
  last_name: u.last_name || '',
  matriculation_no: u.matriculation_no || '',
  labspace_id: u.labspace_id || '',
  lab: u.lab || '',
  telephone: u.telephone || '',
})
const rules = {
  course_id: {
    validator: (_rule, value) => {
      // An explicit check (the stock `required` rule mis-handles numeric ids).
      if (value === null || value === undefined || value === '') {
        return new Error('Please select a course')
      }
      return true
    },
    trigger: ['change', 'blur'],
  },
}
const formRef = ref(null)
const courseOptions = computed(() => courses.value.map((c) => ({ label: c.name, value: c.id })))

async function loadCourses() {
  loadingCourses.value = true
  try {
    courses.value = await api.get('/registration/courses')
  } catch (e) {
    error.value = e.message
  } finally {
    loadingCourses.value = false
  }
}

async function handleComplete() {
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  saving.value = true
  error.value = ''
  try {
    const updated = await api.post('/registration/complete', { ...form.value })
    auth.setUser(updated) // reflect course + generated state
    router.push({ name: 'home' })
  } catch (e) {
    error.value = e.message
  } finally {
    saving.value = false
  }
}

onMounted(loadCourses)
</script>

<style scoped>
.registration-container {
  min-height: 100vh;
  min-height: 100dvh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--fc-space-sm);
  background:
    radial-gradient(120% 90% at 50% 118%, rgba(255, 138, 0, 0.55) 0%, rgba(229, 57, 53, 0.28) 32%, transparent 60%),
    linear-gradient(160deg, #0d1b2a 0%, #12233a 48%, #3a1f1a 100%);
}
.registration-card {
  width: 100%;
  max-width: 640px;
  background: rgba(255, 255, 255, 0.96);
  border-radius: var(--fc-radius-lg);
}
.registration-head {
  margin-bottom: var(--fc-space-md);
}
.registration-title {
  margin: 0 0 4px;
  font-size: var(--fc-fs-lg);
  color: var(--fc-ink);
}
.registration-sub {
  margin: 0;
  font-size: var(--fc-fs-sm);
  color: var(--fc-muted);
}
.registration-error {
  margin-top: var(--fc-space-sm);
}
</style>
