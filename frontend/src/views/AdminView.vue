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
      <!-- Settings is pinned to the far right, with a gear icon. -->
      <n-button
        class="admin-nav__settings"
        :type="isCurrent('admin-settings') ? 'primary' : 'default'"
        secondary
        size="small"
        @click="router.push({ name: 'admin-settings' })"
      >
        <template #icon>
          <svg class="settings-icon" viewBox="0 0 24 24" width="15" height="15" aria-hidden="true">
            <path
              fill="none"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z"
            />
            <path
              fill="none"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M19.4 13a1.65 1.65 0 0 0 .34 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.34 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .34-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.34-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.34h.01a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.34 1.82v.01a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z"
            />
          </svg>
        </template>
        Settings
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
      <HelpSection title="Multiple choice">
        <p>
          In addition to the analyses, students can answer <em>multiple-choice
          cards</em>. The designer is reachable from the <strong>Multiple
          Choice</strong> page (pick a course) or per course under
          <strong>Courses → Multiple Choice</strong>: define <em>questions</em>
          (text, options, one correct answer, plus a description and remarks for
          your own documentation), group up to three questions into a
          <em>card</em>, and present a time-windowed <em>sheet</em> to chosen
          students.
        </p>
        <p>
          Grading is per course (on the same page): points awarded for a fully
          correct card (default 10) and the penalty per wrong answer (default
          2). A card's score is the points minus the penalty times the number
          of wrong answers, floored at zero.
        </p>
      </HelpSection>
      <HelpSection title="Ion symbols">
        <p>
          An ion is written as one canonical symbol:
          <code>formula&nbsp;+&nbsp;sign&nbsp;+&nbsp;magnitude</code>, with the
          digit <em>always</em> present - e.g. <code>Na+1</code>, <code>Mg+2</code>,
          <code>Fe+3</code>, <code>SO4-2</code>, <code>Cl-1</code>. The charge is
          the part from the last <code>+</code>/<code>-</code> to the end, so
          multi-valent cations are unambiguous (<code>Fe+2</code> vs <code>Fe+3</code>).
        </p>
        <p>
          You may type a bare sign (<code>Na+</code>) or paste the IUPAC
          superscript form (<code>SO&#8324;&#178;&#8315;</code>, <code>Mg&#178;&#8314;</code>);
          the system normalizes it to the canonical form and derives the charge
          and cation/anion kind from the symbol.
        </p>
        <p>
          In the UI ions are rendered with the IUPAC superscript
          (magnitude before the sign, unit charge without the 1):
          SO<sub>4</sub><sup>2&#8722;</sup>, Na<sup>+</sup>, Mg<sup>2+</sup>.
        </p>
      </HelpSection>
      <HelpSection title="Substances (CSV import)">
        <p>
          Upload a CSV of substances to grow the catalog. Separate several ions
          or synonyms with a semicolon (e.g. <code>Na+1;Cl-1</code>). Ions use
          the canonical symbol (see "Ion symbols" above). Rows are matched by
          name - a match updates the existing substance.
        </p>
      </HelpSection>
      <HelpSection title="Authentication &amp; registration">
        <p>
          Everyone signs in with a JWT (username/password). Students can
          additionally scan a personal barcode, or - if your course uses OAuth -
          sign in via an external identity provider such as Keycloak.
        </p>
        <p>
          How <em>student</em> accounts are created is set in <strong>Settings
          → Registration</strong>: <code>manual</code> (you create them under
          Courses → Members), <code>self-registration</code> (they register and
          confirm their e-mail) or <code>oauth</code> (they sign in via the
          provider and then complete a registration page).
        </p>
      </HelpSection>
      <HelpSection title="Settings">
        <p>
          Global grading settings (points per ion, penalties, submission limit)
          and the active course. These apply to every analysis.
        </p>
      </HelpSection>
      <AboutSection />
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
import AboutSection from '../components/AboutSection.vue'

const helpOpen = ref(false)

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

// Main nav (left). Settings is rendered separately, pinned to the far right.
// The global "Assignments" page was removed: enrolling students is done at the
// course level (the "Assign" button on each course row), which is more intuitive.
const navItems = [
  { to: 'admin-courses', label: 'Courses' },
  { to: 'admin-types', label: 'Analysis Types' },
  { to: 'admin-substances', label: 'Substances' },
  { to: 'admin-multichoice', label: 'Multiple Choice' },
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
  align-items: center;
  gap: var(--fc-space-xs);
  margin-bottom: var(--fc-space-md);
}

/* Pin the Settings button to the far right of the nav row. */
.admin-nav__settings {
  margin-left: auto;
}

.settings-icon {
  display: block;
}
</style>
