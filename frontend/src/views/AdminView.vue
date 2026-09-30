<template>
  <div class="fc-page">
    <header class="fc-header">
      <h1 class="fc-title">Admin</h1>
      <n-space>
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
  </div>
</template>

<script setup>
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { homeForRole } from '../router'
import { NButton, NSpace } from 'naive-ui'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const navItems = [
  { to: 'admin-settings', label: 'Settings' },
  { to: 'admin-courses', label: 'Courses' },
  { to: 'admin-types', label: 'Analysis Types' },
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
