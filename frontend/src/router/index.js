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
    path: '/register',
    name: 'register',
    component: () => import('../views/RegisterView.vue'),
    meta: { public: true },
  },
  {
    // Landed here after an OAuth sign-in (allauth set a Django session). The
    // component exchanges the session for a JWT; it is public because the user
    // is not JWT-authenticated yet.
    path: '/oauth-callback',
    name: 'oauth-callback',
    component: () => import('../views/OAuthCallbackView.vue'),
    meta: { public: true },
  },
  {
    // OAuth students complete this page (course + metadata + generated analyses)
    // before reaching the student home.
    path: '/registration',
    name: 'registration',
    component: () => import('../views/RegistrationView.vue'),
    meta: { roles: ['student'] },
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
  const needsRegistration =
    auth.isAuthenticated && auth.user?.role === 'student' && auth.user?.registered === false

  if (!to.meta.public && !auth.isAuthenticated) {
    return { name: 'login' }
  }
  if (to.meta.public && auth.isAuthenticated) {
    if (needsRegistration) return { name: 'registration' }
    return { name: homeForRole(auth.user?.role) }
  }
  if (to.meta.roles && auth.user && !to.meta.roles.includes(auth.user.role)) {
    return { name: homeForRole(auth.user.role) }
  }
  // An unregistered student is confined to the registration page.
  if (needsRegistration && !to.meta.public && to.name !== 'registration') {
    return { name: 'registration' }
  }
  // A registered student no longer needs the registration page.
  if (
    auth.isAuthenticated &&
    auth.user?.role === 'student' &&
    auth.user?.registered &&
    to.name === 'registration'
  ) {
    return { name: 'home' }
  }
})

export default router
