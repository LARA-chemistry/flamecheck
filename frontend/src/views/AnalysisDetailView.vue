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
        <n-grid :cols="responsiveCols" :x-gap="16" :y-gap="16" v-if="detail.window_status !== 'submitted'">
          <n-gi>
            <n-card title="Cations" size="small">
              <n-space vertical>
                <n-checkbox-group v-model:value="selectedCations">
                  <n-checkbox
                    v-for="ion in detail.cations"
                    :key="ion.id"
                    :value="ion.id"
                    :label="`${ion.symbol} — ${ion.name}`"
                  />
                </n-checkbox-group>
              </n-space>
            </n-card>
          </n-gi>
          <n-gi>
            <n-card title="Anions" size="small">
              <n-space vertical>
                <n-checkbox-group v-model:value="selectedAnions">
                  <n-checkbox
                    v-for="ion in detail.anions"
                    :key="ion.id"
                    :value="ion.id"
                    :label="`${ion.symbol} — ${ion.name}`"
                  />
                </n-checkbox-group>
              </n-space>
            </n-card>
          </n-gi>
        </n-grid>

        <n-card v-if="detail.window_status === 'open'" style="margin-top: 16px">
          <n-space justify="end">
            <n-button
              type="primary"
              :loading="submitting"
              :disabled="selectedIons.length === 0"
              @click="handleSubmit"
            >
              Submit Analysis ({{ selectedIons.length }} ions)
            </n-button>
          </n-space>
        </n-card>
      </template>

      <!-- Result view -->
      <n-card v-if="result" title="Result" size="large" style="margin-top: 16px">
        <n-descriptions :column="2" label-placement="left">
          <n-descriptions-item label="Score">
            <n-text :type="result.score >= result.ideal_score ? 'success' : 'warning'" style="font-size: 20px">
              {{ result.score }} / {{ result.ideal_score }}
            </n-text>
          </n-descriptions-item>
          <n-descriptions-item label="Submission #">{{ result.submission_number }}</n-descriptions-item>
          <n-descriptions-item label="Correct">{{ result.correct }}</n-descriptions-item>
          <n-descriptions-item label="Wrong">{{ result.wrong }}</n-descriptions-item>
          <n-descriptions-item label="Missing">{{ result.missing }}</n-descriptions-item>
          <n-descriptions-item label="Penalty">-{{ result.penalty }}</n-descriptions-item>
        </n-descriptions>
      </n-card>

      <n-alert v-if="error" type="error" style="margin-top: 12px">{{ error }}</n-alert>
    </n-spin>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/client'
import {
  NCard, NSpace, NButton, NTag, NSpin, NGrid, NGi, NCheckbox, NCheckboxGroup,
  NDescriptions, NDescriptionsItem, NText, NAlert,
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

async function load() {
  loading.value = true
  error.value = ''
  try {
    detail.value = await api.get(`/analyses/${id}`)
    if (detail.value.window_status === 'submitted') {
      result.value = await api.get(`/analyses/${id}/result`)
    }
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function handleSubmit() {
  submitting.value = true
  error.value = ''
  try {
    const res = await api.post(`/analyses/${id}/submissions`, {
      ion_ids: selectedIons.value,
      confirmed: true,
      idempotency_key: crypto.randomUUID(),
    })
    result.value = res
    detail.value.window_status = 'submitted'
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
</style>
