<template>
  <button
    class="help-toggle"
    :class="{ 'help-toggle--active': active }"
    type="button"
    aria-label="Toggle help panel"
    :aria-pressed="String(active)"
    title="Help"
    @click="emit('click')"
  >
    <span class="help-toggle__icon" aria-hidden="true">?</span>
  </button>
</template>

<script setup>
defineProps({
  /** Visual active state (panel is open). */
  active: { type: Boolean, default: false },
})
const emit = defineEmits(['click'])
</script>

<style scoped>
.help-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  border: 1px solid var(--fc-border);
  background: var(--fc-surface);
  color: var(--fc-text-soft);
  cursor: pointer;
  box-shadow: var(--fc-shadow-sm);
  transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;
}
.help-toggle__icon {
  font-weight: 800;
  font-size: var(--fc-fs-sm);
  line-height: 1;
}
.help-toggle:hover {
  color: var(--fc-ink);
  border-color: var(--fc-flame-2);
}
.help-toggle--active {
  background: var(--fc-flame-soft);
  border-color: var(--fc-flame-2);
  color: var(--fc-flame-2);
}
/* Large-screen feature only. */
@media (max-width: 1199px) {
  .help-toggle {
    display: none;
  }
}
</style>
