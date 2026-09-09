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
  },
]

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
    return { name: 'home' }
  }
  if (to.meta.roles && auth.user && !to.meta.roles.includes(auth.user.role)) {
    return { name: 'home' }
  }
})

export default router
