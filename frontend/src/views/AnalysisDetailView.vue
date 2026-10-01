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

      <!-- Result view (full submission history) -->
      <ResultCard
        v-if="result"
        :submissions="result.submissions"
        :total-score="result.total_score"
        :ideal-score="result.ideal_score"
        @back="router.push('/')"
      />

      <n-alert v-if="error" type="error" class="error-alert">{{ error }}</n-alert>
    </n-spin>

    <!-- Submission confirmation -->
    <n-modal v-model:show="confirmShow" preset="card" title="Confirm submission" style="width: 480px; max-width: 92vw">
      <n-space vertical size="medium">
        <n-text>
          You are about to submit <strong>{{ selectedIons.length }}</strong>
          ion{{ selectedIons.length === 1 ? '' : 's' }} for
          <strong>{{ detail?.type }} #{{ detail?.number }}</strong>.
        </n-text>
        <!-- The ions the student is submitting, by name -->
        <div class="confirm-ions">
          <n-tag
            v-for="(label, i) in selectedIonLabels"
            :key="selectedIons[i]"
            :type="isCation(selectedIons[i]) ? 'info' : 'warning'"
            :bordered="false"
            round
          >
            {{ label }}
          </n-tag>
        </div>
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

// Is the given ion id one of the cations (used to colour the confirm tags)?
function isCation(ionId) {
  return (detail.value?.cations || []).some((c) => c.id === ionId)
}

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

// Resolve the selected ion ids to their symbol/name labels (for the confirm
// modal). Cations come first, then anions, matching the selection order.
const selectedIonLabels = computed(() => {
  const byId = new Map()
  for (const ion of [...detail.value?.cations, ...detail.value?.anions] || []) {
    byId.set(ion.id, ion)
  }
  return selectedIons.value.map((ionId) => {
    const ion = byId.get(ionId)
    return ion ? `${ion.symbol} — ${ion.name}` : `ion #${ionId}`
  })
})

function windowTagType(status) {
  const map = { open: 'success', too_early: 'warning', too_late: 'error', submitted: 'info' }
  return map[status] || 'default'
}
function windowLabel(status) {
  const map = { open: 'Open', too_early: 'Not Open Yet', too_late: 'Closed', submitted: 'Submitted' }
  return map[status] || status
}

/**
 * Normalize a submission-history payload into the shape ResultCard consumes:
 * { submissions: [ { id, submission_number, submitted_at, score, penalty,
 *   ideal_score, correct[], wrong[], missing[], correct_count, wrong_count,
 *   missing_count } ], total_score, ideal_score }.
 *
 * Handles both the GET /result payload (full history) and, as a fallback, the
 * just-created submission from the POST payload.
 */
function normalizeResult(payload) {
  if (!payload) return null
  const toSub = (s) => ({
    id: s.id,
    submission_number: s.submission_number,
    submitted_at: s.submitted_at,
    score: s.score,
    penalty: s.penalty ?? 0,
    ideal_score: s.ideal_score,
    correct: s.correct_ions || [],
    wrong: s.wrong_ions || [],
    missing: s.missing_ions || [],
    correct_count: s.correct_count ?? (s.correct_ions || []).length,
    wrong_count: s.wrong_count ?? (s.wrong_ions || []).length,
    missing_count: s.missing_count ?? (s.missing_ions || []).length,
  })
  // GET /result shape: full history.
  if (payload.submissions && payload.submissions.length) {
    return {
      submissions: payload.submissions.map(toSub),
      total_score: payload.total_score,
      ideal_score: payload.ideal_score,
    }
  }
  // POST /submissions shape: just the one created submission.
  if (payload.submission && payload.result) {
    const s = payload.submission
    return {
      submissions: [
        {
          ...toSub(s),
          correct: payload.result.correct_ions || [],
          wrong: payload.result.wrong_ions || [],
          missing: payload.result.missing_ions || [],
        },
      ],
      total_score: payload.result.total_score ?? s.score,
      ideal_score: payload.result.ideal_score ?? s.ideal_score,
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
    await api.post(`/analyses/${id}/submissions`, {
      ion_ids: selectedIons.value,
      confirmed: true,
      idempotency_key: crypto.randomUUID(),
    })
    // Re-fetch the full history so the result view shows every attempt.
    const payload = await api.get(`/analyses/${id}/result`)
    result.value = normalizeResult(payload)
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

.confirm-ions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--fc-space-xs);
  padding: var(--fc-space-sm);
  background: var(--fc-bg);
  border-radius: var(--fc-radius-sm);
}
</style>
