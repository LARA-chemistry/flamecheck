<template>
  <div class="result-card">
    <!-- Overall verdict banner (from the final submission / total score) -->
    <div class="result-card__verdict" :class="passed ? 'result-card__verdict--pass' : 'result-card__verdict--fail'">
      <span class="result-card__icon" aria-hidden="true">
        <!-- Green checkmark (passed) -->
        <svg v-if="passed" viewBox="0 0 52 52" width="46" height="46">
          <circle cx="26" cy="26" r="24" fill="none" stroke="currentColor" stroke-width="3" />
          <path d="M15 27l7 7 15-16" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        <!-- Red cancel / cross (failed) -->
        <svg v-else viewBox="0 0 52 52" width="46" height="46">
          <circle cx="26" cy="26" r="24" fill="none" stroke="currentColor" stroke-width="3" />
          <path d="M18 18l16 16M34 18L18 34" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round" />
        </svg>
      </span>
      <div class="result-card__verdict-text">
        <h3 class="result-card__headline">{{ passed ? 'Passed' : 'Failed' }}</h3>
        <p class="result-card__sub">
          {{ passed
            ? 'You identified the ions correctly in your final attempt.'
            : 'Review the attempts below to see what to add or remove.' }}
        </p>
      </div>
      <div class="result-card__score">
        <span class="result-card__score-value">{{ totalScore }}</span>
        <span class="result-card__score-max">/ {{ idealScore }}</span>
      </div>
    </div>

    <!-- Submission history (final first, then earlier attempts) -->
    <div class="result-card__history">
      <article
        v-for="s in ordered"
        :key="s.id"
        class="attempt"
        :class="s.is_last ? 'attempt--final' : 'attempt--earlier'"
      >
        <header class="attempt__head">
          <span class="attempt__tag" :class="s.is_last ? 'attempt__tag--final' : 'attempt__tag--earlier'">
            {{ s.is_last ? 'Final' : `Attempt #${s.submission_number}` }}
          </span>
          <span class="attempt__verdict" :class="s.score > 0 ? 'attempt__verdict--pass' : 'attempt__verdict--fail'">
            {{ s.score > 0 ? 'Passed' : 'Failed' }}
          </span>
          <span class="attempt__score">
            <strong>{{ s.score }}</strong><small>/ {{ s.ideal_score }}</small>
            <em v-if="s.penalty" class="attempt__penalty">−{{ s.penalty }} penalty</em>
          </span>
        </header>

        <!-- FINAL submission: full correct / wrong / missing breakdown (with ions),
             aligned in a grid and split into cations vs. anions. -->
        <div v-if="s.is_last" class="attempt__breakdown">
          <section class="breakdown-row">
            <h4 class="breakdown-row__label breakdown-row__label--correct">Right</h4>
            <div class="breakdown-row__groups">
              <div class="ion-group">
                <span class="ion-group__kind ion-group__kind--cation">Cations</span>
                <div class="ion-group__tags">
                  <n-tag v-for="ion in splitByKind(s.correct).cations" :key="ion.id" type="success" :bordered="false" round>
                    {{ ion.symbol }}
                  </n-tag>
                  <span v-if="splitByKind(s.correct).cations.length === 0" class="breakdown-row__none">none</span>
                </div>
              </div>
              <div class="ion-group">
                <span class="ion-group__kind ion-group__kind--anion">Anions</span>
                <div class="ion-group__tags">
                  <n-tag v-for="ion in splitByKind(s.correct).anions" :key="ion.id" type="success" :bordered="false" round>
                    {{ ion.symbol }}
                  </n-tag>
                  <span v-if="splitByKind(s.correct).anions.length === 0" class="breakdown-row__none">none</span>
                </div>
              </div>
            </div>
          </section>
          <section class="breakdown-row">
            <h4 class="breakdown-row__label breakdown-row__label--wrong">Wrong</h4>
            <div class="breakdown-row__groups">
              <div class="ion-group">
                <span class="ion-group__kind ion-group__kind--cation">Cations</span>
                <div class="ion-group__tags">
                  <n-tag v-for="ion in splitByKind(s.wrong).cations" :key="ion.id" type="error" :bordered="false" round>
                    {{ ion.symbol }}
                  </n-tag>
                  <span v-if="splitByKind(s.wrong).cations.length === 0" class="breakdown-row__none">none</span>
                </div>
              </div>
              <div class="ion-group">
                <span class="ion-group__kind ion-group__kind--anion">Anions</span>
                <div class="ion-group__tags">
                  <n-tag v-for="ion in splitByKind(s.wrong).anions" :key="ion.id" type="error" :bordered="false" round>
                    {{ ion.symbol }}
                  </n-tag>
                  <span v-if="splitByKind(s.wrong).anions.length === 0" class="breakdown-row__none">none</span>
                </div>
              </div>
            </div>
          </section>
          <section class="breakdown-row">
            <h4 class="breakdown-row__label breakdown-row__label--missing">Missing</h4>
            <div class="breakdown-row__groups">
              <div class="ion-group">
                <span class="ion-group__kind ion-group__kind--cation">Cations</span>
                <div class="ion-group__tags">
                  <n-tag v-for="ion in splitByKind(s.missing).cations" :key="ion.id" type="warning" :bordered="false" round>
                    {{ ion.symbol }}
                  </n-tag>
                  <span v-if="splitByKind(s.missing).cations.length === 0" class="breakdown-row__none">none</span>
                </div>
              </div>
              <div class="ion-group">
                <span class="ion-group__kind ion-group__kind--anion">Anions</span>
                <div class="ion-group__tags">
                  <n-tag v-for="ion in splitByKind(s.missing).anions" :key="ion.id" type="warning" :bordered="false" round>
                    {{ ion.symbol }}
                  </n-tag>
                  <span v-if="splitByKind(s.missing).anions.length === 0" class="breakdown-row__none">none</span>
                </div>
              </div>
            </div>
          </section>
        </div>

        <!-- EARLIER submissions: only how many to add (missing) / remove (wrong) -->
        <p v-else class="attempt__hint" :class="{ 'attempt__hint--done': s.missing_count === 0 && s.wrong_count === 0 }">
          <template v-if="s.missing_count === 0 && s.wrong_count === 0">
            Nothing to add or remove — the selection was complete for this attempt.
          </template>
          <template v-else>
            <span v-if="s.missing_count > 0">
              Add <strong>{{ s.missing_count }}</strong> ion{{ s.missing_count === 1 ? '' : 's' }}
            </span>
            <span v-if="s.missing_count > 0 && s.wrong_count > 0"> and </span>
            <span v-if="s.wrong_count > 0">
              remove <strong>{{ s.wrong_count }}</strong> ion{{ s.wrong_count === 1 ? '' : 's' }}
            </span>
          </template>
        </p>
      </article>
    </div>

    <div class="result-card__foot">
      <n-button size="small" secondary @click="$emit('back')">← Back to my analyses</n-button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { NTag, NButton } from 'naive-ui'

const props = defineProps({
  /**
   * Normalized submission list, each:
   * { id, submission_number, submitted_at, score, penalty, ideal_score,
   *   correct[], wrong[], missing[], correct_count, wrong_count, missing_count }
   * The entry with the highest submission_number is treated as the "final"
   * one and gets the full breakdown; earlier ones show add/remove counts only.
   */
  submissions: { type: Array, required: true },
  /** Overall total score (best/last per the grading strategy). */
  totalScore: { type: Number, required: true },
  /** Overall ideal score. */
  idealScore: { type: Number, required: true },
})
defineEmits(['back'])

// Final submission = the one with the highest submission_number.
const finalNumber = computed(() =>
  props.submissions.reduce((max, s) => Math.max(max, s.submission_number), 0),
)
// Newest first: the final attempt is shown at the top, earlier ones below.
const ordered = computed(() =>
  [...props.submissions]
    .map((s) => ({ ...s, is_last: s.submission_number === finalNumber.value }))
    .sort((a, b) => b.submission_number - a.submission_number),
)
const passed = computed(() => props.totalScore > 0)

// Split a list of ions into { cations: [], anions: [] } (by ion.kind).
function splitByKind(ions) {
  const out = { cations: [], anions: [] }
  for (const ion of ions || []) {
    if (ion.kind === 'anion') out.anions.push(ion)
    else out.cations.push(ion)
  }
  return out
}
</script>

<style scoped>
.result-card {
  border-radius: var(--fc-radius-lg);
  border: 1px solid var(--fc-border);
  background: var(--fc-surface);
  box-shadow: var(--fc-shadow);
  padding: var(--fc-space-lg);
  display: flex;
  flex-direction: column;
  gap: var(--fc-space-lg);
}

/* Verdict banner ---------------------------------------------------------- */
.result-card__verdict {
  display: flex;
  align-items: center;
  gap: var(--fc-space-md);
  padding: var(--fc-space-md);
  border-radius: var(--fc-radius);
  flex-wrap: wrap;
}
.result-card__verdict--pass {
  background: rgba(46, 125, 50, 0.1);
  border: 1px solid rgba(46, 125, 50, 0.35);
}
.result-card__verdict--fail {
  background: rgba(229, 57, 53, 0.08);
  border: 1px solid rgba(229, 57, 53, 0.3);
}
.result-card__icon {
  display: inline-flex;
  flex-shrink: 0;
}
.result-card__verdict--pass .result-card__icon {
  color: #2e7d32;
}
.result-card__verdict--fail .result-card__icon {
  color: #e53935;
}
.result-card__verdict-text {
  flex: 1 1 auto;
  min-width: 160px;
}
.result-card__headline {
  font-size: var(--fc-fs-lg);
  font-weight: 800;
  margin: 0;
  line-height: 1.1;
}
.result-card__verdict--pass .result-card__headline {
  color: #2e7d32;
}
.result-card__verdict--fail .result-card__headline {
  color: #e53935;
}
.result-card__sub {
  margin: 4px 0 0;
  font-size: var(--fc-fs-sm);
  color: var(--fc-text-soft);
}
.result-card__score {
  display: flex;
  align-items: baseline;
  gap: 2px;
  flex-shrink: 0;
  padding-left: var(--fc-space-sm);
  border-left: 1px solid var(--fc-border);
}
.result-card__score-value {
  font-size: var(--fc-fs-hero);
  font-weight: 800;
  line-height: 1;
  color: var(--fc-ink);
}
.result-card__score-max {
  font-size: var(--fc-fs-md);
  font-weight: 600;
  color: var(--fc-muted);
}

/* Submission history ------------------------------------------------------- */
.result-card__history {
  display: flex;
  flex-direction: column;
  gap: var(--fc-space-sm);
}
.attempt {
  border: 1px solid var(--fc-border);
  border-radius: var(--fc-radius);
  padding: var(--fc-space-sm) var(--fc-space-md);
  display: flex;
  flex-direction: column;
  gap: var(--fc-space-sm);
  background: var(--fc-bg);
}
.attempt--final {
  border-color: rgba(255, 138, 0, 0.4);
  background: linear-gradient(180deg, rgba(255, 243, 224, 0.7), var(--fc-bg));
}
.attempt__head {
  display: flex;
  align-items: center;
  gap: var(--fc-space-sm);
  flex-wrap: wrap;
}
.attempt__tag {
  font-size: var(--fc-fs-xs);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 3px 9px;
  border-radius: 999px;
}
.attempt__tag--final {
  background: var(--fc-flame-soft);
  color: var(--fc-flame-2);
}
.attempt__tag--earlier {
  background: rgba(138, 148, 166, 0.16);
  color: var(--fc-text-soft);
}
.attempt__verdict {
  font-size: var(--fc-fs-sm);
  font-weight: 700;
}
.attempt__verdict--pass {
  color: #2e7d32;
}
.attempt__verdict--fail {
  color: #e53935;
}
.attempt__score {
  margin-left: auto;
  font-size: var(--fc-fs-md);
  font-weight: 800;
  color: var(--fc-ink);
  display: inline-flex;
  align-items: baseline;
  gap: 3px;
}
.attempt__score small {
  font-size: var(--fc-fs-sm);
  font-weight: 600;
  color: var(--fc-muted);
}
.attempt__penalty {
  font-size: var(--fc-fs-xs);
  color: var(--fc-text-soft);
  font-style: normal;
  margin-left: 6px;
}

/* Full breakdown (final attempt) ------------------------------------------ */
.attempt__breakdown {
  display: flex;
  flex-direction: column;
  gap: var(--fc-space-sm);
}
.breakdown-row {
  display: grid;
  grid-template-columns: 92px 1fr;
  gap: var(--fc-space-sm);
  align-items: center;
  padding: var(--fc-space-sm);
  border-radius: var(--fc-radius-sm);
  background: var(--fc-surface);
}
.breakdown-row__label {
  font-size: var(--fc-fs-sm);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin: 0;
}
.breakdown-row__label--correct {
  color: #2e7d32;
}
.breakdown-row__label--wrong {
  color: #e53935;
}
.breakdown-row__label--missing {
  color: #f57c00;
}
/* Cation / anion groups within a breakdown row. */
.breakdown-row__groups {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--fc-space-sm);
  align-items: start;
  min-width: 0;
}
.ion-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.ion-group__kind {
  font-size: var(--fc-fs-xs);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--fc-text-soft);
}
.ion-group__kind--cation {
  color: #1565c0;
}
.ion-group__kind--anion {
  color: #6a1b9a;
}
.ion-group__tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--fc-space-xs);
}
.breakdown-row__none {
  font-size: var(--fc-fs-sm);
  color: var(--fc-muted);
  font-style: italic;
}

/* Add/remove hint (earlier attempts) -------------------------------------- */
.attempt__hint {
  margin: 0;
  font-size: var(--fc-fs-base);
  color: var(--fc-text);
  background: var(--fc-surface);
  border-radius: var(--fc-radius-sm);
  padding: var(--fc-space-sm) var(--fc-space-md);
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}
.attempt__hint strong {
  color: var(--fc-flame-2);
  font-size: var(--fc-fs-md);
}
.attempt__hint--done {
  color: #2e7d32;
}

.result-card__foot {
  display: flex;
  justify-content: flex-start;
}

@media (max-width: 520px) {
  .breakdown-row {
    grid-template-columns: 1fr;
    gap: var(--fc-space-xs);
  }
  .breakdown-row__groups {
    grid-template-columns: 1fr;
    gap: var(--fc-space-xs);
  }
  .result-card__score {
    border-left: none;
    padding-left: 0;
    width: 100%;
    justify-content: flex-end;
  }
  .attempt__score {
    margin-left: 0;
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
