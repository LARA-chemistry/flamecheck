<script setup>
import { ref, computed, watch } from 'vue'
import { NModal, NSpin, NTag, NEmpty, NScrollbar, NButton, NAlert } from 'naive-ui'
import { api } from '../api/client'
import IonSymbol from './IonSymbol.vue'

const props = defineProps({
  show: { type: Boolean, required: true },
  user: { type: Object, required: true },
  analyses: { type: Array, required: true },
  // Time-windowed multiple-choice sheets (the student's /mc-sheets payload).
  mcSheets: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:show'])

const loading = ref(false)
const error = ref('')
// Full result breakdown per analysis id, fetched lazily for submitted analyses:
// { [analysisId]: { submissions: [...], total_score, ideal_score } | null }
const results = ref({})
// Which submitted analyses the user has expanded (to reveal the ion breakdown).
const expanded = ref({})

// The analyses that already have a submission — these are the ones with a real
// result to show (everything else is in-flight / not yet open).
const submittedAnalyses = computed(() =>
  props.analyses.filter((a) => a.window_status === 'submitted'),
)

// Multiple-choice state: which submitted sheets are expanded, the lazily
// fetched per-sheet detail (questions with revealed answers + the graded
// result) and per-sheet loading flags. Details are only fetched on first
// expand — a course can have many sheets, so the list stays cheap.
const expandedMc = ref({})
const mcDetails = ref({})
const mcLoading = ref({})

const submittedMc = computed(() => props.mcSheets.filter((m) => m.window_status === 'submitted'))

async function fetchMcDetail(sheet) {
  mcLoading.value = { ...mcLoading.value, [sheet.id]: true }
  try {
    const payload = await api.get(`/mc-sheets/${sheet.id}`)
    mcDetails.value = { ...mcDetails.value, [sheet.id]: payload }
  } catch {
    mcDetails.value = { ...mcDetails.value, [sheet.id]: null }
  } finally {
    mcLoading.value = { ...mcLoading.value, [sheet.id]: false }
  }
}

function toggleExpandMc(sheet) {
  expandedMc.value = { ...expandedMc.value, [sheet.id]: !expandedMc.value[sheet.id] }
  if (expandedMc.value[sheet.id] && !mcDetails.value[sheet.id] && !mcLoading.value[sheet.id]) {
    fetchMcDetail(sheet)
  }
}
function onMcHeadClick(sheet) {
  if (sheet.window_status === 'submitted') toggleExpandMc(sheet)
}

// Per-question lookup into the fetched detail (result.per_question maps
// question id -> selected/correct option ids + verdict).
function mcPq(sheet, q) {
  return (mcDetails.value[sheet.id]?.result?.per_question || []).find((p) => p.question_id === q.id)
}
function mcSelectedText(sheet, q) {
  const pq = mcPq(sheet, q)
  if (!pq) return null
  const opt = (q.options || []).find((o) => o.id === pq.selected_option_id)
  return opt ? opt.text : '?'
}
function mcIsCorrect(sheet, q) {
  return !!mcPq(sheet, q)?.is_correct
}
function mcCorrectText(q) {
  return (q.options || []).find((o) => o.is_correct)?.text || '—'
}

async function fetchResults() {
  if (submittedAnalyses.value.length === 0) {
    results.value = {}
    return
  }
  loading.value = true
  error.value = ''
  try {
    const settled = await Promise.allSettled(
      submittedAnalyses.value.map(async (a) => {
        const payload = await api.get(`/analyses/${a.id}/result`)
        return [a.id, normalizeResult(payload)]
      }),
    )
    const next = {}
    for (const res of settled) {
      if (res.status === 'fulfilled') next[res.value[0]] = res.value[1]
    }
    results.value = next
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

// Shape a GET /analyses/{id}/result payload into { submissions, total_score,
// ideal_score } with the ion breakdowns ResultCard-style consumers expect.
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
  return {
    submissions: (payload.submissions || []).map(toSub),
    total_score: payload.total_score,
    ideal_score: payload.ideal_score,
  }
}

function toggleExpand(id) {
  expanded.value = { ...expanded.value, [id]: !expanded.value[id] }
}
function onHeadClick(a) {
  if (a.window_status === 'submitted') toggleExpand(a.id)
}

// Id of the final submission of a result (the highest submission_number),
// or null when there is none. Used to mark which attempt shows the breakdown.
function finalId(result) {
  if (!result || !result.submissions.length) return null
  return result.submissions.reduce((max, s) =>
    s.submission_number > max.submission_number ? s : max,
  ).id
}
function splitByKind(ions) {
  const out = { cations: [], anions: [] }
  for (const ion of ions || []) {
    if (ion.kind === 'anion') out.anions.push(ion)
    else out.cations.push(ion)
  }
  return out
}

function windowTagType(status) {
  const map = { open: 'success', too_early: 'warning', too_late: 'error', submitted: 'info' }
  return map[status] || 'default'
}
function windowLabel(status) {
  const map = { open: 'Open', too_early: 'Not Open Yet', too_late: 'Closed', submitted: 'Submitted' }
  return map[status] || status
}
function fmtDateTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleString(undefined, {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// Core profile rows (label/value); an empty value renders as an em dash.
const coreRows = computed(() => {
  const u = props.user || {}
  return [
    ['Name', u.full_name || u.username || '—'],
    ['Matriculation no.', u.matriculation_no || '—'],
    ['Labspace id', u.labspace_id || '—'],
    ['Telephone', u.telephone || '—'],
    ['Course', u.course_name || '—'],
  ]
})

// Reload results each time the modal opens.
watch(
  () => props.show,
  (val) => {
    if (val) {
      expanded.value = {}
      expandedMc.value = {}
      mcDetails.value = {}
      mcLoading.value = {}
      fetchResults()
    }
  },
)
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    title="Your profile"
    :closable="true"
    @update:show="emit('update:show', $event)"
    style="width: 720px; max-width: 94vw"
  >
    <div class="profile">
      <!-- Core data -------------------------------------------------------- -->
      <section class="profile__core">
        <div class="profile__avatar" aria-hidden="true">
          {{ (user?.full_name || user?.username || '?').charAt(0).toUpperCase() }}
        </div>
        <dl class="profile__rows">
          <div v-for="[label, value] in coreRows" :key="label" class="profile__row">
            <dt class="profile__label">{{ label }}</dt>
            <dd class="profile__value">{{ value }}</dd>
          </div>
        </dl>
      </section>

      <!-- Analysis results ------------------------------------------------- -->
      <section class="profile__results">
        <h3 class="profile__section-title">
          Analysis results
          <span class="profile__section-count">{{ submittedAnalyses.length }} of {{ analyses.length }} submitted</span>
        </h3>

        <n-empty v-if="analyses.length === 0" description="No analyses assigned yet." size="small" />

        <template v-else>
          <n-spin :show="loading">
            <n-scrollbar style="max-height: 46vh; min-height: 120px">
              <div class="profile__list">
                <article
                  v-for="a in analyses"
                  :key="a.id"
                  class="result-row"
                  :class="{ 'result-row--expandable': a.window_status === 'submitted' }"
                >
                  <header class="result-row__head" @click="onHeadClick(a)">
                    <span class="result-row__num">#{{ a.number }}</span>
                    <h4 class="result-row__title">{{ a.type }}</h4>
                    <n-tag :type="windowTagType(a.window_status)" round size="small">
                      {{ windowLabel(a.window_status) }}
                    </n-tag>
                    <span
                      v-if="a.window_status === 'submitted'"
                      class="result-row__score"
                    >
                      <strong>{{ results[a.id]?.total_score ?? a.score ?? '—' }}</strong>
                      <small>/ {{ results[a.id]?.ideal_score ?? a.submission_limit ?? '—' }}</small>
                    </span>
                    <svg
                      v-if="a.window_status === 'submitted'"
                      class="result-row__chevron"
                      :class="{ 'result-row__chevron--open': expanded[a.id] }"
                      viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"
                    >
                      <path d="M6 9l6 6 6-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
                    </svg>
                  </header>

                  <!-- Submitted: show the final attempt + breakdown (expandable) -->
                  <div v-if="a.window_status === 'submitted'" class="result-row__body">
                    <div v-if="!expanded[a.id]" class="result-row__summary">
                      <template v-if="results[a.id] && results[a.id].submissions.length">
                        <span class="result-row__meta">
                          {{ results[a.id].submissions.length }} submission{{ results[a.id].submissions.length === 1 ? '' : 's' }}
                          <template v-if="results[a.id].submissions.length > 1">
                            · final:
                            <span
                              :class="results[a.id].submissions.at(-1).score > 0 ? 'result-row__meta--pass' : 'result-row__meta--fail'"
                            >
                              {{ results[a.id].submissions.at(-1).score > 0 ? 'Passed' : 'Failed' }}
                            </span>
                          </template>
                        </span>
                        <button class="result-row__link" @click="toggleExpand(a.id)">Show breakdown</button>
                      </template>
                      <span v-else class="result-row__meta">Result not yet available.</span>
                    </div>

                    <div v-else class="result-row__detail">
                      <template v-for="s in (results[a.id]?.submissions || [])" :key="s.id">
                        <!-- Final attempt: full cation/anion breakdown -->
                        <div
                          v-if="s.id === finalId(results[a.id])"
                          class="breakdown"
                        >
                          <div class="breakdown__head">
                            <span class="breakdown__tag">Final · Attempt #{{ s.submission_number }}</span>
                            <span class="breakdown__at" v-if="s.submitted_at">{{ fmtDateTime(s.submitted_at) }}</span>
                          </div>
                          <div class="breakdown__rows">
                            <div class="breakdown__group breakdown__group--correct">
                              <span class="breakdown__kind">Right</span>
                              <div class="breakdown__ions">
                                <n-tag v-for="ion in splitByKind(s.correct).cations" :key="ion.id" type="success" :bordered="false" round size="small"><IonSymbol :symbol="ion.symbol" /></n-tag>
                                <n-tag v-for="ion in splitByKind(s.correct).anions" :key="ion.id" type="success" :bordered="false" round size="small"><IonSymbol :symbol="ion.symbol" /></n-tag>
                                <span v-if="!s.correct?.length" class="breakdown__none">none</span>
                              </div>
                            </div>
                            <div class="breakdown__group breakdown__group--wrong">
                              <span class="breakdown__kind">Wrong</span>
                              <div class="breakdown__ions">
                                <n-tag v-for="ion in splitByKind(s.wrong).cations" :key="ion.id" type="error" :bordered="false" round size="small"><IonSymbol :symbol="ion.symbol" /></n-tag>
                                <n-tag v-for="ion in splitByKind(s.wrong).anions" :key="ion.id" type="error" :bordered="false" round size="small"><IonSymbol :symbol="ion.symbol" /></n-tag>
                                <span v-if="!s.wrong?.length" class="breakdown__none">none</span>
                              </div>
                            </div>
                            <div class="breakdown__group breakdown__group--missing">
                              <span class="breakdown__kind">Missing</span>
                              <div class="breakdown__ions">
                                <n-tag v-for="ion in splitByKind(s.missing).cations" :key="ion.id" type="warning" :bordered="false" round size="small"><IonSymbol :symbol="ion.symbol" /></n-tag>
                                <n-tag v-for="ion in splitByKind(s.missing).anions" :key="ion.id" type="warning" :bordered="false" round size="small"><IonSymbol :symbol="ion.symbol" /></n-tag>
                                <span v-if="!s.missing?.length" class="breakdown__none">none</span>
                              </div>
                            </div>
                          </div>
                        </div>
                        <!-- Earlier attempts: one-line add/remove hint -->
                        <p
                          v-if="s.id !== finalId(results[a.id])"
                          class="result-row__earlier"
                          :class="{ 'result-row__earlier--done': s.missing_count === 0 && s.wrong_count === 0 }"
                        >
                          Attempt #{{ s.submission_number }}
                          <template v-if="s.missing_count === 0 && s.wrong_count === 0">— complete</template>
                          <template v-else>
                            <template v-if="s.missing_count > 0">add {{ s.missing_count }}</template>
                            <template v-if="s.missing_count > 0 && s.wrong_count > 0">, </template>
                            <template v-if="s.wrong_count > 0">remove {{ s.wrong_count }}</template>
                          </template>
                        </p>
                      </template>
                      <button class="result-row__link" @click="toggleExpand(a.id)">Hide breakdown</button>
                    </div>
                  </div>

                  <!-- Not submitted: a short status note -->
                  <div v-else class="result-row__note">
                    {{ a.window_status === 'too_early' ? 'Opens ' + (a.window_start ? fmtDateTime(a.window_start) : 'soon') : a.window_status === 'too_late' ? 'Window closed' : 'Window open — submit when ready.' }}
                  </div>
                </article>
              </div>
            </n-scrollbar>
          </n-spin>

          <n-alert v-if="error" type="error" :show-icon="false" style="margin-top: var(--fc-space-sm)">
            {{ error }}
          </n-alert>
        </template>
      </section>

      <!-- Multiple-choice results ------------------------------------------ -->
      <section v-if="mcSheets.length" class="profile__results">
        <h3 class="profile__section-title">
          Multiple choice results
          <span class="profile__section-count">{{ submittedMc.length }} of {{ mcSheets.length }} submitted</span>
        </h3>

        <n-scrollbar style="max-height: 46vh; min-height: 120px">
          <div class="profile__list">
            <article
              v-for="m in mcSheets"
              :key="m.id"
              class="result-row"
              :class="{ 'result-row--expandable': m.window_status === 'submitted' }"
            >
              <header class="result-row__head" @click="onMcHeadClick(m)">
                <span class="result-row__num">MC #{{ m.number }}</span>
                <h4 class="result-row__title">{{ m.card_title }}</h4>
                <n-tag :type="windowTagType(m.window_status)" round size="small">
                  {{ windowLabel(m.window_status) }}
                </n-tag>
                <span v-if="m.window_status === 'submitted'" class="result-row__score">
                  <strong>{{ m.score ?? '—' }}</strong>
                  <small v-if="mcDetails[m.id]?.result">/ {{ mcDetails[m.id].result.ideal_score }}</small>
                </span>
                <svg
                  v-if="m.window_status === 'submitted'"
                  class="result-row__chevron"
                  :class="{ 'result-row__chevron--open': expandedMc[m.id] }"
                  viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"
                >
                  <path d="M6 9l6 6 6-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
                </svg>
              </header>

              <!-- Submitted: per-question breakdown (fetched on expand) -->
              <div v-if="m.window_status === 'submitted'" class="result-row__body">
                <div v-if="!expandedMc[m.id]" class="result-row__summary">
                  <span class="result-row__meta">
                    <template v-if="mcDetails[m.id]?.result">
                      {{ mcDetails[m.id].result.correct_count }} right · {{ mcDetails[m.id].result.wrong_count }} wrong
                      <template v-if="mcDetails[m.id].result.submitted_at"> · {{ fmtDateTime(mcDetails[m.id].result.submitted_at) }}</template>
                    </template>
                    <template v-else>Score {{ m.score ?? '—' }}</template>
                  </span>
                  <button class="result-row__link" @click="toggleExpandMc(m)">Show breakdown</button>
                </div>

                <div v-else class="result-row__detail">
                  <div v-if="mcLoading[m.id]" class="result-row__note">Loading…</div>
                  <div v-else-if="!mcDetails[m.id]" class="result-row__note">Result not yet available.</div>
                  <template v-else>
                    <div v-for="q in mcDetails[m.id].questions" :key="q.id" class="mcq">
                      <p class="mcq__text">{{ q.text }}</p>
                      <div class="mcq__answers">
                        <n-tag :type="mcIsCorrect(m, q) ? 'success' : 'error'" :bordered="false" round size="small">
                          {{ mcSelectedText(m, q) }}
                        </n-tag>
                        <template v-if="!mcIsCorrect(m, q)">
                          <span class="mcq__correct-label">correct:</span>
                          <n-tag type="success" :bordered="false" round size="small">{{ mcCorrectText(q) }}</n-tag>
                        </template>
                      </div>
                    </div>
                    <button class="result-row__link" @click="toggleExpandMc(m)">Hide breakdown</button>
                  </template>
                </div>
              </div>

              <!-- Not submitted: a short status note -->
              <div v-else class="result-row__note">
                {{ m.window_status === 'too_early' ? 'Opens ' + (m.window_start ? fmtDateTime(m.window_start) : 'soon') : m.window_status === 'too_late' ? 'Window closed' : 'Window open — submit when ready.' }}
              </div>
            </article>
          </div>
        </n-scrollbar>
      </section>
    </div>

    <template #footer>
      <n-button secondary block @click="emit('update:show', false)">Close</n-button>
    </template>
  </n-modal>
</template>

<style scoped>
.profile {
  display: flex;
  flex-direction: column;
  gap: var(--fc-space-md);
}

/* Core data -------------------------------------------------------------- */
.profile__core {
  display: flex;
  gap: var(--fc-space-md);
  align-items: flex-start;
  padding: var(--fc-space-md);
  border-radius: var(--fc-radius);
  background: linear-gradient(135deg, var(--fc-flame-soft), var(--fc-surface));
  border: 1px solid var(--fc-border);
}
.profile__avatar {
  width: 56px;
  height: 56px;
  border-radius: 16px;
  background: var(--fc-flame-gradient);
  color: #fff;
  font-size: var(--fc-fs-lg);
  font-weight: 800;
  display: grid;
  place-items: center;
  flex-shrink: 0;
}
.profile__rows {
  margin: 0;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--fc-space-xs) var(--fc-space-md);
  flex: 1 1 auto;
  min-width: 0;
}
.profile__row {
  min-width: 0;
}
.profile__label {
  font-size: var(--fc-fs-xs);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--fc-muted);
}
.profile__value {
  margin: 2px 0 0;
  font-size: var(--fc-fs-base);
  font-weight: 600;
  color: var(--fc-ink);
  overflow-wrap: anywhere;
}

/* Results ---------------------------------------------------------------- */
.profile__section-title {
  font-size: var(--fc-fs-md);
  font-weight: 700;
  margin: 0 0 var(--fc-space-sm);
  display: flex;
  align-items: baseline;
  gap: var(--fc-space-xs);
}
.profile__section-count {
  font-size: var(--fc-fs-xs);
  font-weight: 600;
  color: var(--fc-muted);
}
.profile__list {
  display: flex;
  flex-direction: column;
  gap: var(--fc-space-sm);
  padding-right: var(--fc-space-xs);
}

.result-row {
  border: 1px solid var(--fc-border);
  border-radius: var(--fc-radius);
  background: var(--fc-surface);
  overflow: hidden;
}
.result-row--expandable .result-row__head {
  cursor: pointer;
  user-select: none;
}
.result-row__head {
  display: flex;
  align-items: center;
  gap: var(--fc-space-sm);
  padding: var(--fc-space-sm) var(--fc-space-md);
  flex-wrap: wrap;
}
.result-row__num {
  font-size: var(--fc-fs-xs);
  font-weight: 700;
  color: var(--fc-muted);
}
.result-row__title {
  margin: 0;
  font-size: var(--fc-fs-base);
  font-weight: 700;
  flex: 1 1 auto;
  min-width: 0;
}
.result-row__score {
  display: inline-flex;
  align-items: baseline;
  gap: 2px;
  font-weight: 800;
  font-size: var(--fc-fs-md);
  color: var(--fc-ink);
}
.result-row__score small {
  font-size: var(--fc-fs-sm);
  font-weight: 600;
  color: var(--fc-muted);
}
.result-row__chevron {
  color: var(--fc-muted);
  transition: transform 0.18s ease;
  flex-shrink: 0;
}
.result-row__chevron--open {
  transform: rotate(180deg);
}
.result-row__body,
.result-row__note {
  padding: 0 var(--fc-space-md) var(--fc-space-sm);
}
.result-row__note {
  font-size: var(--fc-fs-sm);
  color: var(--fc-text-soft);
  padding-top: 0;
}
.result-row__summary,
.result-row__detail {
  display: flex;
  align-items: center;
  gap: var(--fc-space-sm);
  flex-wrap: wrap;
}
.result-row__detail {
  flex-direction: column;
  align-items: stretch;
  gap: var(--fc-space-xs);
}
.result-row__meta {
  font-size: var(--fc-fs-sm);
  color: var(--fc-text-soft);
}
.result-row__meta--pass {
  color: #2e7d32;
  font-weight: 700;
}
.result-row__meta--fail {
  color: #e53935;
  font-weight: 700;
}
.result-row__link {
  border: none;
  background: none;
  color: var(--fc-flame-2);
  font-size: var(--fc-fs-sm);
  font-weight: 700;
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 6px;
}
.result-row__link:hover {
  background: var(--fc-flame-soft);
}
.result-row__earlier {
  margin: 0;
  font-size: var(--fc-fs-sm);
  color: var(--fc-text-soft);
  padding: 2px 4px;
}
.result-row__earlier--done {
  color: #2e7d32;
}

/* Ion breakdown ---------------------------------------------------------- */
.breakdown {
  display: flex;
  flex-direction: column;
  gap: var(--fc-space-xs);
}
.breakdown__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--fc-space-sm);
}
.breakdown__tag {
  font-size: var(--fc-fs-xs);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 3px 9px;
  border-radius: 999px;
  background: var(--fc-flame-soft);
  color: var(--fc-flame-2);
}
.breakdown__at {
  font-size: var(--fc-fs-xs);
  color: var(--fc-muted);
}
.breakdown__rows {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.breakdown__group {
  display: grid;
  grid-template-columns: 72px 1fr;
  gap: var(--fc-space-sm);
  align-items: center;
  padding: var(--fc-space-xs) var(--fc-space-sm);
  border-radius: var(--fc-radius-sm);
  background: var(--fc-bg);
}
.breakdown__kind {
  font-size: var(--fc-fs-xs);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.breakdown__group--correct .breakdown__kind { color: #2e7d32; }
.breakdown__group--wrong .breakdown__kind { color: #e53935; }
.breakdown__group--missing .breakdown__kind { color: #f57c00; }
.breakdown__ions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--fc-space-xs);
  min-width: 0;
}
.breakdown__none {
  font-size: var(--fc-fs-sm);
  color: var(--fc-muted);
  font-style: italic;
}

/* Multiple-choice per-question rows --------------------------------------- */
.mcq {
  display: flex;
  flex-direction: column;
  gap: var(--fc-space-xs);
  padding: var(--fc-space-xs) var(--fc-space-sm);
  border-radius: var(--fc-radius-sm);
  background: var(--fc-bg);
}
.mcq__text {
  margin: 0;
  font-size: var(--fc-fs-sm);
  font-weight: 600;
  color: var(--fc-ink);
}
.mcq__answers {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--fc-space-xs);
}
.mcq__correct-label {
  font-size: var(--fc-fs-xs);
  font-weight: 600;
  color: var(--fc-muted);
}

@media (max-width: 520px) {
  .profile__core {
    flex-direction: column;
    align-items: center;
    text-align: center;
  }
  .profile__rows {
    grid-template-columns: 1fr;
    width: 100%;
  }
  .breakdown__group {
    grid-template-columns: 1fr;
    gap: 4px;
  }
}
</style>
