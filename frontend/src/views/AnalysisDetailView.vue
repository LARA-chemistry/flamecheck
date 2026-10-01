<template>
  <div class="fc-page">
    <header class="fc-header">
      <n-space align="center">
        <n-button quaternary size="small" @click="router.push('/')">← Back</n-button>
        <h2 class="fc-title">{{ detail?.type }} <span class="analysis-num">#{{ detail?.number }}</span></h2>
      </n-space>
      <n-tag v-if="detail" :type="windowTagType(detail.window_status)" round>
        {{ windowLabel(detail.window_status) }}
      </n-tag>
    </header>

    <n-spin :show="loading">
      <template v-if="detail">
        <!-- Editable ion selection (only before submission) -->
        <n-grid :cols="responsiveCols" :x-gap="20" :y-gap="20" v-if="!result">
          <n-gi>
            <n-card title="Cations" size="small">
              <n-space vertical size="medium">
                <n-checkbox-group v-model:value="selectedCations">
                  <n-checkbox
                    v-for="ion in detail.cations"
                    :key="ion.id"
                    :value="ion.id"
                    :label="`${ion.symbol} — ${ion.name}`"
                    class="ion-check"
                  />
                </n-checkbox-group>
                <n-empty v-if="detail.cations.length === 0" description="No cations" size="small" />
              </n-space>
            </n-card>
          </n-gi>
          <n-gi>
            <n-card title="Anions" size="small">
              <n-space vertical size="medium">
                <n-checkbox-group v-model:value="selectedAnions">
                  <n-checkbox
                    v-for="ion in detail.anions"
                    :key="ion.id"
                    :value="ion.id"
                    :label="`${ion.symbol} — ${ion.name}`"
                    class="ion-check"
                  />
                </n-checkbox-group>
                <n-empty v-if="detail.anions.length === 0" description="No anions" size="small" />
              </n-space>
            </n-card>
          </n-gi>
        </n-grid>

        <!-- Submit bar (only while the window is open and nothing submitted yet) -->
        <n-card v-if="!result && detail.window_status === 'open'" class="submit-bar">
          <n-space justify="space-between" align="center" :wrap="true">
            <n-text depth="3">
              {{ selectedIons.length }} ion{{ selectedIons.length === 1 ? '' : 's' }} selected
            </n-text>
            <n-button
              type="primary"
              size="large"
              :loading="submitting"
              :disabled="selectedIons.length === 0"
              @click="confirmShow = true"
            >
              Submit Analysis
            </n-button>
          </n-space>
        </n-card>
      </template>

      <!-- Result view -->
      <ResultCard v-if="result" :result="result" @back="router.push('/')" />

      <n-alert v-if="error" type="error" class="error-alert">{{ error }}</n-alert>
    </n-spin>

    <!-- Submission confirmation -->
    <n-modal v-model:show="confirmShow" preset="card" title="Confirm submission" style="width: 460px; max-width: 92vw">
      <n-space vertical size="medium">
        <n-text>
          You are about to submit <strong>{{ selectedIons.length }}</strong>
          ion{{ selectedIons.length === 1 ? '' : 's' }} for
          <strong>{{ detail?.type }} #{{ detail?.number }}</strong>.
        </n-text>
        <n-alert type="warning" :bordered="false">
          This counts against your submission limit ({{ detail?.submission_count }}/{{ detail?.submission_limit }} used).
          Please make sure your selection is final.
        </n-alert>
      </n-space>
      <template #footer>
        <n-space justify="end">
          <n-button @click="confirmShow = false">Cancel</n-button>
          <n-button type="primary" :loading="submitting" @click="doSubmit">Confirm &amp; Submit</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/client'
import ResultCard from '../components/ResultCard.vue'
import {
  NCard, NSpace, NButton, NTag, NSpin, NGrid, NGi, NCheckbox, NCheckboxGroup,
  NText, NAlert, NModal, NEmpty,
} from 'naive-ui'

const route = useRoute()
const router = useRouter()
const id = route.params.id

// Responsive ion grid: single column on phones, two columns on larger screens.
const isNarrow = ref(window.innerWidth < 620)
function onResize() {
  isNarrow.value = window.innerWidth < 620
}
const responsiveCols = computed(() => (isNarrow.value ? 1 : 2))
onMounted(() => window.addEventListener('resize', onResize))
onBeforeUnmount(() => window.removeEventListener('resize', onResize))

const loading = ref(true)
const submitting = ref(false)
const confirmShow = ref(false)
const error = ref('')
const detail = ref(null)
const result = ref(null)
const selectedCations = ref([])
const selectedAnions = ref([])

const selectedIons = computed(() => [...selectedCations.value, ...selectedAnions.value])

function windowTagType(status) {
  const map = { open: 'success', too_early: 'warning', too_late: 'error', submitted: 'info' }
  return map[status] || 'default'
}
function windowLabel(status) {
  const map = { open: 'Open', too_early: 'Not Open Yet', too_late: 'Closed', submitted: 'Submitted' }
  return map[status] || status
}

/**
 * Normalize the two different result payloads (the just-created submission and
 * the GET /result history) into a single shape the ResultCard consumes:
 * { passed, score, ideal_score, submission_number, correct[], wrong[], missing[] }.
 */
function normalizeResult(payload) {
  if (!payload) return null
  // Submit POST shape: { submission, result }
  if (payload.submission && payload.result) {
    const s = payload.submission
    return {
      passed: s.score > 0,
      score: s.score,
      ideal_score: s.ideal_score,
      submission_number: s.submission_number,
      penalty: s.penalty,
      correct: payload.result.correct_ions || [],
      wrong: payload.result.wrong_ions || [],
      missing: payload.result.missing_ions || [],
    }
  }
  // GET /result shape: { submissions: [...], total_score, ideal_score }
  if (payload.submissions && payload.submissions.length) {
    const latest = payload.submissions[payload.submissions.length - 1]
    return {
      passed: latest.score > 0,
      score: latest.score,
      ideal_score: latest.ideal_score,
      submission_number: latest.submission_number,
      penalty: latest.penalty,
      correct: latest.correct_ions || [],
      wrong: latest.wrong_ions || [],
      missing: latest.missing_ions || [],
    }
  }
  return null
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    detail.value = await api.get(`/analyses/${id}`)
    if (detail.value.window_status === 'submitted') {
      const payload = await api.get(`/analyses/${id}/result`)
      result.value = normalizeResult(payload)
    }
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function doSubmit() {
  submitting.value = true
  error.value = ''
  try {
    const res = await api.post(`/analyses/${id}/submissions`, {
      ion_ids: selectedIons.value,
      confirmed: true,
      idempotency_key: crypto.randomUUID(),
    })
    result.value = normalizeResult(res)
    detail.value.window_status = 'submitted'
    confirmShow.value = false
  } catch (e) {
    error.value = e.message
  } finally {
    submitting.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.analysis-num {
  color: var(--fc-flame-2);
  font-weight: 800;
}

:deep(.n-card) {
  border-radius: var(--fc-radius);
}

.ion-check {
  font-size: var(--fc-fs-base);
}

.submit-bar {
  margin-top: var(--fc-space-md);
}

.error-alert {
  margin-top: var(--fc-space-sm);
}
</style>
