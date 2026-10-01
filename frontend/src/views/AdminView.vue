<template>
  <div class="fc-page">
    <header class="fc-header">
      <h1 class="fc-title">Admin</h1>
      <n-space align="center">
        <HelpToggle :active="helpOpen" @click="helpOpen = !helpOpen" />
        <n-button size="small" secondary tag="a" href="/admin-django/" target="_blank" rel="noopener">
          Django admin
        </n-button>
        <n-button size="small" secondary @click="handleLogout">Logout</n-button>
      </n-space>
    </header>

    <nav class="admin-nav">
      <n-button
        v-for="item in navItems"
        :key="item.to"
        :type="isCurrent(item.to) ? 'primary' : 'default'"
        secondary
        size="small"
        @click="router.push({ name: item.to })"
      >
        {{ item.label }}
      </n-button>
    </nav>

    <router-view />

    <HelpPanel v-model:open="helpOpen" title="Admin help">
      <HelpSection title="Overview">
        <p>
          Manage courses, analysis types, the ion/substance catalog and student
          assignments. Most actions here change what students see, so double-check
          before you apply them.
        </p>
      </HelpSection>
      <HelpSection title="Courses &amp; assignments">
        <p>
          Enroll students in a course, then assign an analysis (announcement) to
          them. Each student gets their own sheet; use the assignment page to
          manage who receives which analysis and to roll random sample
          compositions.
        </p>
      </HelpSection>
      <HelpSection title="Analysis types &amp; instances">
        <p>
          A <em>type</em> defines the possible ion set (what students may select).
          A concrete <em>instance</em> for a course/announcement holds the hidden
          answer key and the submission window.
        </p>
      </HelpSection>
      <HelpSection title="Substances (CSV import)">
        <p>
          Upload a CSV of substances to grow the catalog. Separate several ions
          or synonyms with a semicolon (e.g. <code>Na+;Cl-</code>). Rows are
          matched by name - a match updates the existing substance.
        </p>
      </HelpSection>
      <HelpSection title="Settings">
        <p>
          Global grading settings (points per ion, penalties, submission limit)
          and the active course. These apply to every analysis.
        </p>
      </HelpSection>
    </HelpPanel>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { homeForRole } from '../router'
import { NButton, NSpace } from 'naive-ui'
import HelpPanel from '../components/HelpPanel.vue'
import HelpToggle from '../components/HelpToggle.vue'
import HelpSection from '../components/HelpSection.vue'

const helpOpen = ref(false)

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const navItems = [
  { to: 'admin-settings', label: 'Settings' },
  { to: 'admin-courses', label: 'Courses' },
  { to: 'admin-types', label: 'Analysis Types' },
  { to: 'admin-substances', label: 'Substances' },
  { to: 'admin-assignments', label: 'Assignments' },
]

function isCurrent(name) {
  return route.name === name
}

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.admin-nav {
  display: flex;
  flex-wrap: wrap;
  gap: var(--fc-space-xs);
  margin-bottom: var(--fc-space-md);
}
</style>
