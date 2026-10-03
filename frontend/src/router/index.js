import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/LoginView.vue'),
    meta: { public: true },
  },
  {
    path: '/',
    name: 'home',
    component: () => import('../views/StudentView.vue'),
    meta: { roles: ['student'] },
  },
  {
    path: '/analysis/:id',
    name: 'analysis',
    component: () => import('../views/AnalysisDetailView.vue'),
    meta: { roles: ['student'] },
  },
  {
    // Same component in "results" mode: the full submission history / result.
    // Reached only explicitly (card "Results" button, or after the last
    // allowed submission) - opening a card that still has submissions left
    // shows the submission view instead.
    path: '/analysis/:id/results',
    name: 'analysis-results',
    component: () => import('../views/AnalysisDetailView.vue'),
    meta: { roles: ['student'] },
  },
  {
    path: '/assistant',
    name: 'assistant',
    component: () => import('../views/AssistantView.vue'),
    meta: { roles: ['assistant', 'admin'] },
  },
  {
    path: '/admin',
    name: 'admin',
    component: () => import('../views/AdminView.vue'),
    meta: { roles: ['admin'] },
    redirect: { name: 'admin-courses' },
    children: [
      {
        path: 'settings',
        name: 'admin-settings',
        component: () => import('../views/AdminSettingsView.vue'),
        meta: { roles: ['admin'] },
      },
      {
        path: 'courses',
        name: 'admin-courses',
        component: () => import('../views/AdminCoursesView.vue'),
        meta: { roles: ['admin'] },
      },
      {
        path: 'analysis-types',
        name: 'admin-types',
        component: () => import('../views/AdminTypesView.vue'),
        meta: { roles: ['admin'] },
      },
      {
        path: 'substances',
        name: 'admin-substances',
        component: () => import('../views/AdminSubstancesView.vue'),
        meta: { roles: ['admin'] },
      },
      {
        path: 'assignments',
        name: 'admin-assignments',
        component: () => import('../views/AdminAssignView.vue'),
        meta: { roles: ['admin'] },
      },
    ],
  },
]

/**
 * Map a user role to the route name of their landing page.
 *
 * Each role has a dedicated dashboard: students land on the analysis home,
 * assistants on the assistant dashboard, admins on the admin panel.
 *
 * @param {string} role - The user's role (`student`, `assistant` or `admin`).
 * @returns {string} The route name to navigate to for that role.
 */
export function homeForRole(role) {
  switch (role) {
    case 'assistant':
      return 'assistant'
    case 'admin':
      return 'admin'
    case 'student':
    default:
      return 'home'
  }
}

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.isAuthenticated) {
    return { name: 'login' }
  }
  if (to.meta.public && auth.isAuthenticated) {
    return { name: homeForRole(auth.user?.role) }
  }
  if (to.meta.roles && auth.user && !to.meta.roles.includes(auth.user.role)) {
    return { name: homeForRole(auth.user.role) }
  }
})

export default router
