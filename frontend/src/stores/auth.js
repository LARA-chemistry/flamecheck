import { defineStore } from 'pinia'
import { api } from '../api/client'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: JSON.parse(localStorage.getItem('fc_user') || 'null'),
    accessToken: localStorage.getItem('fc_access') || null,
    refreshToken: localStorage.getItem('fc_refresh') || null,
  }),
  getters: {
    isAuthenticated: (state) => !!state.accessToken,
    role: (state) => state.user?.role || 'student',
  },
  actions: {
    setTokens(accessToken, refreshToken) {
      this.accessToken = accessToken
      this.refreshToken = refreshToken
      localStorage.setItem('fc_access', accessToken)
      localStorage.setItem('fc_refresh', refreshToken)
    },
    setUser(user) {
      this.user = user
      localStorage.setItem('fc_user', JSON.stringify(user))
    },
    async login(username, password) {
      const res = await api.post('/auth/login', { username, password })
      this.setTokens(res.access, res.refresh)
      const me = await api.get('/me')
      this.setUser(me)
      return me
    },
    async scanBarcode(barcode) {
      const res = await api.post('/auth/barcode/scan', { barcode })
      this.setTokens(res.access, res.refresh)
      const me = await api.get('/me')
      this.setUser(me)
      return me
    },
    async refresh() {
      const res = await api.post('/auth/token/refresh', { refresh: this.refreshToken }, { raw: true })
      this.setTokens(res.access, res.refresh)
    },
    logout() {
      try {
        api.post('/auth/logout', {})
      } catch {
        /* ignore */
      }
      this.user = null
      this.accessToken = null
      this.refreshToken = null
      localStorage.removeItem('fc_access')
      localStorage.removeItem('fc_refresh')
      localStorage.removeItem('fc_user')
    },
  },
})
