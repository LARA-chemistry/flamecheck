<template>
  <div class="fc-page mc-page">
    <header class="mc-head">
      <n-button size="small" secondary @click="goHome">← Back</n-button>
      <div class="mc-head__titles">
        <h1 class="fc-title">{{ detail?.card_title || 'Card' }} <span v-if="detail" class="mc-num">#{{ detail.number }}</span></h1>
        <p v-if="detail" class="mc-window">
          <n-tag :type="windowTagType(detail.window_status)" round size="small">{{ windowLabel(detail.window_status) }}</n-tag>
          <span class="mc-window__interval">{{ windowInterval(detail) }}</span>
        </p>
      </div>
    </header>

    <n-spin :show="loading">
      <div v-if="detail" class="mc-body">
        <!-- Result (after a submission exists) -->
        <template v-if="detail.result">
          <n-alert
            :type="detail.result.score >= detail.result.ideal_score ? 'success' : 'warning'"
            title="Result"
            class="mc-result"
          >
            <div class="mc-result__score">
              <span class="mc-result__value">{{ detail.result.score }}</span>
              <span class="mc-result__label">of {{ detail.result.ideal_score }} points</span>
            </div>
            <p class="mc-result__note">
              {{ detail.result.correct_count }} correct, {{ detail.result.wrong_count }} wrong.
            </p>
          </n-alert>
          <div class="mc-questions">
            <section v-for="(q, qi) in detail.questions" :key="q.id" class="mc-question">
              <h3 class="mc-question__title">{{ qi + 1 }}. {{ q.text }}</h3>
              <div class="mc-question__options">
                <div
                  v-for="opt in q.options"
                  :key="opt.id"
                  class="mc-option"
                  :class="{
                    'mc-option--correct': opt.is_correct,
                    'mc-option--chosen': resultChoice(q.id) === opt.id,
                    'mc-option--wrong': resultChoice(q.id) === opt.id && !opt.is_correct,
                  }"
                >
                  <span class="mc-option__text">{{ opt.text }}</span>
                  <span v-if="opt.is_correct" class="mc-option__badge mc-option__badge--correct">Correct</span>
                  <span v-else-if="resultChoice(q.id) === opt.id" class="mc-option__badge mc-option__badge--wrong">Your answer</span>
                </div>
              </div>
            </section>
          </div>
        </template>

        <!-- Answer form (no submission yet) -->
        <template v-else>
          <p v-if="detail.window_status !== 'open'" class="mc-closed">
            {{ detail.window_status === 'too_early' ? 'This card is not open yet.' : 'This card has closed.' }}
          </p>
          <div v-else class="mc-questions">
            <section v-for="(q, qi) in detail.questions" :key="q.id" class="mc-question">
              <h3 class="mc-question__title">{{ qi + 1 }}. {{ q.text }}</h3>
              <n-radio-group v-model:value="answers[q.id]">
                <div class="mc-question__options">
                  <label v-for="opt in q.options" :key="opt.id" class="mc-option mc-option--input">
                    <n-radio :value="opt.id" />
                    <span class="mc-option__text">{{ opt.text }}</span>
                  </label>
                </div>
              </n-radio-group>
            </section>
          </div>
          <div class="mc-actions">
            <n-button type="primary" :disabled="!allAnswered" :loading="submitting" @click="submit">
              Submit answers
            </n-button>
            <n-text v-if="!allAnswered" depth="3" class="mc-actions__hint">Answer all {{ detail.questions.length }} question(s).</n-text>
          </div>
        </template>
      </div>
    </n-spin>

    <n-alert v-if="message" :type="msgType" closable @close="message = ''">{{ message }}</n-alert>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/client'
import { NSpin, NButton, NTag, NAlert, NRadioGroup, NRadio, NText } from 'naive-ui'

const route = useRoute()
const router = useRouter()
const sheetId = Number(route.params.id)

const loading = ref(true)
const detail = ref(null)
const answers = ref({})
const submitting = ref(false)
const message = ref('')
const msgType = ref('success')

const allAnswered = computed(() => {
  const qs = detail.value?.questions || []
  return qs.length > 0 && qs.every((q) => answers.value[q.id] != null)
})

function windowTagType(status) {
  const map = { open: 'success', too_early: 'warning', too_late: 'error', submitted: 'info' }
  return map[status] || 'default'
}
function windowLabel(status) {
  const map = { open: 'Open', too_early: 'Not Open Yet', too_late: 'Closed', submitted: 'Submitted' }
  return map[status] || status
}
function windowInterval(d) {
  if (!d?.window_start || !d?.window_end) return ''
  const s = new Date(d.window_start)
  const e = new Date(d.window_end)
  const day = (x) => x.toLocaleDateString(undefined, { day: '2-digit', month: 'short' })
  const time = (x) => x.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
  return s.toDateString() === e.toDateString()
    ? `${day(s)} · ${time(s)} – ${time(e)}`
    : `${day(s)} · ${time(s)} – ${day(e)} · ${time(e)}`
}
// The option the student chose for a question (from the stored submission).
function resultChoice(questionId) {
  const pq = (detail.value?.result?.per_question || []).find((p) => p.question_id === questionId)
  return pq ? pq.selected_option_id : null
}

async function load() {
  loading.value = true
  try {
    detail.value = await api.get(`/mc-sheets/${sheetId}`)
    if (!detail.value.result) {
      // Pre-select nothing; the student chooses.
      answers.value = {}
    }
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  } finally {
    loading.value = false
  }
}

async function submit() {
  if (!allAnswered.value) return
  submitting.value = true
  try {
    const payload = {
      answers: Object.fromEntries(Object.entries(answers.value).map(([k, v]) => [String(k), Number(v)])),
      idempotency_key: (crypto.randomUUID ? crypto.randomUUID() : String(Date.now())),
    }
    await api.post(`/mc-sheets/${sheetId}/submissions`, payload)
    message.value = 'Answers submitted.'
    msgType.value = 'success'
    await load()
  } catch (e) {
    message.value = e.message
    msgType.value = 'error'
  } finally {
    submitting.value = false
  }
}

function goHome() {
  router.push('/')
}

onMounted(load)
</script>

<style scoped>
.mc-page { display: flex; flex-direction: column; gap: var(--fc-space-md); }
.mc-head { display: flex; align-items: flex-start; gap: var(--fc-space-sm); }
.mc-head__titles { flex: 1 1 auto; }
.mc-num { color: var(--fc-flame-2); }
.mc-window { display: flex; align-items: center; gap: var(--fc-space-xs); margin: 4px 0 0; }
.mc-window__interval { font-size: var(--fc-fs-sm); color: var(--fc-text-soft); }
.mc-body { display: flex; flex-direction: column; gap: var(--fc-space-md); }
.mc-result { align-self: flex-start; min-width: 260px; }
.mc-result__score { display: flex; align-items: baseline; gap: 6px; }
.mc-result__value { font-size: var(--fc-fs-lg, 20px); font-weight: 800; }
.mc-result__label { font-size: var(--fc-fs-xs); color: var(--fc-text-soft); }
.mc-result__note { margin: 6px 0 0; font-size: var(--fc-fs-sm); }
.mc-closed { font-size: var(--fc-fs-sm); color: var(--fc-text-soft); }
.mc-questions { display: flex; flex-direction: column; gap: var(--fc-space-md); }
.mc-question__title { margin: 0 0 var(--fc-space-xs); font-size: var(--fc-fs-md); font-weight: 700; color: var(--fc-ink); }
.mc-question__options { display: flex; flex-direction: column; gap: var(--fc-space-xs); }
.mc-option {
  display: flex; align-items: center; gap: var(--fc-space-xs);
  padding: 10px 12px; border: 1px solid var(--fc-border); border-radius: var(--fc-radius, 10px);
  background: var(--fc-surface);
}
.mc-option--input { cursor: pointer; }
.mc-option--input:hover { border-color: var(--fc-flame-2); }
.mc-option__text { flex: 1 1 auto; }
.mc-option__badge { font-size: var(--fc-fs-xs); font-weight: 700; padding: 2px 8px; border-radius: 999px; }
.mc-option__badge--correct { background: rgba(34, 197, 94, 0.16); color: #15803d; }
.mc-option__badge--wrong { background: rgba(239, 68, 68, 0.14); color: #b91c1c; }
.mc-option--correct { border-color: #22c55e; }
.mc-option--wrong { border-color: #ef4444; }
.mc-actions { display: flex; align-items: center; gap: var(--fc-space-sm); }
.mc-actions__hint { font-size: var(--fc-fs-sm); }
</style>
