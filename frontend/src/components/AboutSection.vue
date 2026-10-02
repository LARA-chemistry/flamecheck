<template>
  <HelpSection title="About">
    <p>
      FlameCheck <span class="about-version">{{ version || '—' }}</span> is a web-based
      submission system for the qualitative flame-test analysis practicum.
    </p>
    <p>
      <span class="muted">Repository</span>
      <a :href="repoUrl" target="_blank" rel="noopener">{{ repoUrl }}</a>
    </p>
    <p>
      <span class="muted">Author</span>
      <a :href="authorEmailHref" target="_blank" rel="noopener">{{ authorName }}</a>
      <span class="muted">({{ authorEmail }})</span>
    </p>
  </HelpSection>
</template>

<script setup>
import { computed } from 'vue'
import { useAuthStore } from '../stores/auth'
import HelpSection from './HelpSection.vue'

const auth = useAuthStore()

// The running version is carried by the authenticated user payload
// (UserOut.version, set from flamecheck.__version__).
const version = computed(() => auth.user?.version || '')

const repoUrl = 'https://gitlab.com/opensourcelab/cheminformatics/flamecheck'
const authorName = 'mark doerr'
const authorEmail = 'mark.doerr@uni-greifswald.de'
const authorEmailHref = `mailto:${authorEmail}`
</script>

<style scoped>
.about-version {
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  color: var(--fc-ink);
}
.muted {
  color: var(--fc-muted);
}
a {
  color: var(--fc-flame-2);
  text-decoration: none;
  word-break: break-all;
}
a:hover {
  text-decoration: underline;
}
</style>
