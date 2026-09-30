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
      // The login endpoint returns { tokens: { access, refresh, ... }, user, analyses }.
      const res = await api.post('/auth/login', { username, password })
      const tokens = res.tokens ?? {}
      this.setTokens(tokens.access, tokens.refresh)
      // The login response already carries the authenticated user, so no
      // separate /me round-trip is needed.
      this.setUser(res.user ?? (await api.get('/me')))
      return res.user
    },
    async refresh() {
      // The refresh endpoint returns a flat TokenPairOut ({ access, refresh, ... }).
      // `raw: true` keeps this call out of the client's 401 auto-refresh retry
      // (preventing an infinite refresh loop); we parse the JSON body ourselves.
      const response = await api.post('/auth/token/refresh', { refresh: this.refreshToken }, { raw: true })
      const res = await response.json()
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
