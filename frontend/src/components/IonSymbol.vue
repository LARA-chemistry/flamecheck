<script setup>
// Renders a canonical ion symbol with subscripts (formula digits) and an IUPAC
// superscript charge (magnitude-then-sign). Use it anywhere an ion symbol is
// shown to the user, e.g. <IonSymbol :symbol="ion.symbol" />.
import { computed } from 'vue'
import { ionToHtml } from '../utils/ion'

const props = defineProps({
  /** Canonical ion symbol, e.g. "SO4-2" or "Na+1". */
  symbol: { type: String, required: true },
})

const html = computed(() => ionToHtml(props.symbol))
</script>

<template>
  <span class="ion-symbol" v-html="html"></span>
</template>

<style scoped>
.ion-symbol {
  white-space: nowrap;
}
.ion-symbol :deep(sub),
.ion-symbol :deep(sup) {
  font-size: 0.7em;
}
</style>
