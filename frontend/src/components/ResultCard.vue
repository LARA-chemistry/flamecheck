<template>
  <div class="result-card" :class="result.passed ? 'result-card--pass' : 'result-card--fail'">
    <!-- Verdict banner -->
    <div class="result-card__verdict">
      <span class="result-card__icon" aria-hidden="true">
        <!-- Green checkmark (passed) -->
        <svg v-if="result.passed" viewBox="0 0 52 52" width="46" height="46">
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
        <h3 class="result-card__headline">{{ result.passed ? 'Passed' : 'Failed' }}</h3>
        <p class="result-card__sub">
          {{ result.passed
            ? 'You identified the ions correctly.'
            : 'No correct ions in this attempt - try the breakdown below.' }}
        </p>
      </div>
      <div class="result-card__score">
        <span class="result-card__score-value">{{ result.score }}</span>
        <span class="result-card__score-max">/ {{ result.ideal_score }}</span>
      </div>
    </div>

    <div class="result-card__meta">
      <span class="result-card__meta-item">Submission #{{ result.submission_number }}</span>
      <span v-if="result.penalty" class="result-card__meta-item">Penalty -{{ result.penalty }}</span>
    </div>

    <!-- Ion breakdown -->
    <div class="result-card__breakdown">
      <section class="breakdown-row">
        <h4 class="breakdown-row__label breakdown-row__label--correct">Correct</h4>
        <div class="breakdown-row__tags">
          <n-tag v-for="ion in result.correct" :key="ion.id" type="success" :bordered="false" round>
            {{ ion.symbol }}
          </n-tag>
          <span v-if="result.correct.length === 0" class="breakdown-row__none">none</span>
        </div>
      </section>
      <section class="breakdown-row">
        <h4 class="breakdown-row__label breakdown-row__label--wrong">Wrong</h4>
        <div class="breakdown-row__tags">
          <n-tag v-for="ion in result.wrong" :key="ion.id" type="error" :bordered="false" round>
            {{ ion.symbol }}
          </n-tag>
          <span v-if="result.wrong.length === 0" class="breakdown-row__none">none</span>
        </div>
      </section>
      <section class="breakdown-row">
        <h4 class="breakdown-row__label breakdown-row__label--missing">Missing</h4>
        <div class="breakdown-row__tags">
          <n-tag v-for="ion in result.missing" :key="ion.id" type="warning" :bordered="false" round>
            {{ ion.symbol }}
          </n-tag>
          <span v-if="result.missing.length === 0" class="breakdown-row__none">none</span>
        </div>
      </section>
    </div>

    <div class="result-card__foot">
      <n-button size="small" secondary @click="$emit('back')">← Back to my analyses</n-button>
    </div>
  </div>
</template>

<script setup>
import { NTag, NButton } from 'naive-ui'

defineProps({
  /**
   * Normalized result:
   * { passed, score, ideal_score, submission_number, penalty, correct[], wrong[], missing[] }
   */
  result: { type: Object, required: true },
})
defineEmits(['back'])
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
.result-card--pass .result-card__verdict {
  background: rgba(46, 125, 50, 0.1);
  border: 1px solid rgba(46, 125, 50, 0.35);
}
.result-card--fail .result-card__verdict {
  background: rgba(229, 57, 53, 0.08);
  border: 1px solid rgba(229, 57, 53, 0.3);
}
.result-card__icon {
  display: inline-flex;
  flex-shrink: 0;
}
.result-card--pass .result-card__icon {
  color: #2e7d32;
}
.result-card--fail .result-card__icon {
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
.result-card--pass .result-card__headline {
  color: #2e7d32;
}
.result-card--fail .result-card__headline {
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

/* Meta row ---------------------------------------------------------------- */
.result-card__meta {
  display: flex;
  gap: var(--fc-space-md);
  flex-wrap: wrap;
  font-size: var(--fc-fs-sm);
  color: var(--fc-text-soft);
}
.result-card__meta-item {
  background: var(--fc-bg);
  border-radius: var(--fc-radius-sm);
  padding: 4px 10px;
}

/* Ion breakdown ------------------------------------------------------------ */
.result-card__breakdown {
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
  background: var(--fc-bg);
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
.breakdown-row__tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--fc-space-xs);
}
.breakdown-row__none {
  font-size: var(--fc-fs-sm);
  color: var(--fc-muted);
  font-style: italic;
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
  .result-card__score {
    border-left: none;
    padding-left: 0;
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
