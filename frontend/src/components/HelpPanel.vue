<template>
  <div class="help-panel" :class="{ 'help-panel--open': open }" :style="{ width: open ? panelWidth + 'px' : '0px' }">
    <!-- Drag handle (resizes the panel width) -->
    <div
      v-if="open"
      class="help-panel__handle"
      role="separator"
      aria-orientation="vertical"
      aria-label="Resize help panel"
      tabindex="0"
      @pointerdown="onDragStart"
      @keydown.left.prevent="nudgeWidth(-8)"
      @keydown.right.prevent="nudgeWidth(8)"
    ></div>

    <div class="help-panel__inner" v-if="open">
      <div class="help-panel__head">
        <h2 class="help-panel__title">{{ title }}</h2>
        <button class="help-panel__close" aria-label="Close help panel" @click="emit('update:open', false)">
          <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
            <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
          </svg>
        </button>
      </div>
      <div class="help-panel__body">
        <slot />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  /** Panel heading shown in the header bar. */
  title: { type: String, required: true },
  /** Whether the panel is open (v-model:open). */
  open: { type: Boolean, default: false },
})

const emit = defineEmits(['update:open'])

// Panel width in px. Resizable via the left-edge handle; persisted per user.
const STORAGE_KEY = 'fc-help-panel-width'
const MIN_WIDTH = 280
const MAX_WIDTH = 720
const DEFAULT_WIDTH = 380

function storedWidth() {
  const raw = Number.parseInt(localStorage.getItem(STORAGE_KEY) ?? '', 10)
  if (Number.isFinite(raw) && raw >= MIN_WIDTH && raw <= MAX_WIDTH) return raw
  return DEFAULT_WIDTH
}

const panelWidth = ref(storedWidth())

function clamp(w) {
  return Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, w))
}

function nudgeWidth(delta) {
  panelWidth.value = clamp(panelWidth.value + delta)
}

// ---- pointer-driven resizing ----------------------------------------------
let dragging = false
let startX = 0
let startWidth = 0

function onDragStart(event) {
  dragging = true
  startX = event.clientX
  startWidth = panelWidth.value
  event.preventDefault()
  window.addEventListener('pointermove', onDragMove)
  window.addEventListener('pointerup', onDragEnd)
  document.body.classList.add('help-panel--resizing')
}

function onDragMove(event) {
  if (!dragging) return
  // The panel is on the right; dragging the handle left (negative dx) widens it.
  const dx = startX - event.clientX
  panelWidth.value = clamp(startWidth + dx)
}

function onDragEnd() {
  dragging = false
  window.removeEventListener('pointermove', onDragMove)
  window.removeEventListener('pointerup', onDragEnd)
  document.body.classList.remove('help-panel--resizing')
  try {
    localStorage.setItem(STORAGE_KEY, String(panelWidth.value))
  } catch {
    /* storage unavailable (private mode) - ignore */
  }
}

onMounted(() => {
  try {
    panelWidth.value = storedWidth()
  } catch {
    /* ignore */
  }
})

onBeforeUnmount(() => {
  if (dragging) onDragEnd()
})

// Persist on close too (in case the user resized while it was open).
watch(
  () => props.open,
  (isOpen) => {
    if (!isOpen) {
      try {
        localStorage.setItem(STORAGE_KEY, String(panelWidth.value))
      } catch {
        /* ignore */
      }
    }
  },
)
</script>

<style scoped>
.help-panel {
  position: fixed;
  top: 0;
  right: 0;
  height: 100vh;
  width: 0;
  overflow: hidden;
  background: var(--fc-surface);
  border-left: 1px solid var(--fc-border);
  box-shadow: -6px 0 24px rgba(13, 27, 42, 0.1);
  z-index: 40;
  transition: width 0.22s ease;
}
.help-panel--resizing ~ * {
  /* no-op; body class disables the transition while dragging */
}
.help-panel--open {
  transition: none; /* width changes are user-driven while open */
}
/* Only offered on large screens. */
@media (max-width: 1199px) {
  .help-panel {
    display: none;
  }
}

.help-panel__inner {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
}

.help-panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--fc-space-xs);
  padding: var(--fc-space-sm) var(--fc-space-sm) var(--fc-space-sm) var(--fc-space-md);
  border-bottom: 1px solid var(--fc-border);
  flex: 0 0 auto;
}
.help-panel__title {
  font-size: var(--fc-fs-md);
  font-weight: 700;
  color: var(--fc-ink);
  margin: 0;
}
.help-panel__close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--fc-text-soft);
  cursor: pointer;
}
.help-panel__close:hover {
  background: var(--fc-flame-soft);
  color: var(--fc-ink);
}

.help-panel__body {
  flex: 1 1 auto;
  overflow-y: auto;
  padding: var(--fc-space-sm) var(--fc-space-md);
}

.help-panel__handle {
  position: absolute;
  top: 0;
  left: -3px;
  width: 8px;
  height: 100%;
  cursor: col-resize;
  z-index: 2;
}
.help-panel__handle::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 3px;
  height: 44px;
  border-radius: 3px;
  background: var(--fc-border);
  opacity: 0;
  transition: opacity 0.15s ease, background 0.15s ease;
}
.help-panel__handle:hover::after,
.help-panel__handle:focus-visible::after {
  opacity: 1;
  background: var(--fc-flame-2);
}
.help-panel__handle:focus-visible {
  outline: 2px solid var(--fc-flame-2);
  outline-offset: -2px;
}
</style>

<style>
/* Global (unscoped): disable the width transition + set resize cursor while dragging. */
body.help-panel--resizing {
  cursor: col-resize;
  user-select: none;
}
body.help-panel--resizing .help-panel {
  transition: none !important;
}
</style>
