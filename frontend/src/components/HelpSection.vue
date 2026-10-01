<template>
  <section class="help-section">
    <h3 class="help-section__title" v-html="title" />
    <div class="help-section__body">
      <slot />
    </div>
  </section>
</template>

<script setup>
defineProps({
  /** Section heading (HTML-allowed). */
  title: { type: String, required: true },
})
</script>

<style scoped>
.help-section {
  margin-bottom: var(--fc-space-md);
}
.help-section__title {
  font-size: var(--fc-fs-sm);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--fc-flame-2);
  margin: 0 0 var(--fc-space-xs);
}
.help-section__body {
  font-size: var(--fc-fs-sm);
  color: var(--fc-text);
  line-height: 1.55;
}
.help-section__body p {
  margin: 0 0 var(--fc-space-xs);
}
.help-section__body p:last-child {
  margin-bottom: 0;
}
.help-section__body code {
  background: rgba(127, 127, 127, 0.14);
  padding: 0 4px;
  border-radius: 4px;
  font-size: 0.92em;
}
</style>
