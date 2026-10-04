import { defineStore } from 'pinia'
import { api } from '../api/client'

// Refresh the access token this long before it actually expires, so a request
// never goes out with an already-expired token (which would 401 first).
const REFRESH_BUFFER_MS = 2 * 60 * 1000

// A single in-flight refresh shared by all concurrent callers, so a burst of
// expiring requests triggers exactly one /auth/token/refresh call.
let refreshPromise = null

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: JSON.parse(localStorage.getItem('fc_user') || 'null'),
    accessToken: localStorage.getItem('fc_access') || null,
    refreshToken: localStorage.getItem('fc_refresh') || null,
    // Epoch ms at which the current access token expires (null if unknown,
    // e.g. a session that predates expiry tracking).
    tokenExpiresAt: Number(localStorage.getItem('fc_access_expires') || 0) || null,
  }),
  getters: {
    isAuthenticated: (state) => !!state.accessToken,
    role: (state) => state.user?.role || 'student',
    // True when the access token is missing, already expired, or will expire
    // within the buffer. Callers refresh proactively before sending a request.
    needsTokenRefresh: (state) => {
      if (!state.accessToken) return false
      if (state.tokenExpiresAt === null) return false
      return Date.now() >= state.tokenExpiresAt - REFRESH_BUFFER_MS
    },
  },
  actions: {
    setTokens(accessToken, refreshToken, expiresInSeconds = null) {
      this.accessToken = accessToken
      this.refreshToken = refreshToken
      localStorage.setItem('fc_access', accessToken)
      localStorage.setItem('fc_refresh', refreshToken)
      if (expiresInSeconds) {
        this.tokenExpiresAt = Date.now() + Number(expiresInSeconds) * 1000
        localStorage.setItem('fc_access_expires', String(this.tokenExpiresAt))
      } else {
        this.tokenExpiresAt = null
        localStorage.removeItem('fc_access_expires')
      }
    },
    setUser(user) {
      this.user = user
      localStorage.setItem('fc_user', JSON.stringify(user))
    },
    async login(username, password) {
      // The login endpoint returns { tokens: { access, refresh, ... }, user, analyses }.
      const res = await api.post('/auth/login', { username, password })
      const tokens = res.tokens ?? {}
      this.setTokens(tokens.access, tokens.refresh, tokens.access_expires_in)
      // The login response already carries the authenticated user, so no
      // separate /me round-trip is needed.
      this.setUser(res.user ?? (await api.get('/me')))
      return res.user
    },
    async refresh() {
      // Serialize concurrent refreshes: share one in-flight request.
      if (refreshPromise) return refreshPromise
      refreshPromise = (async () => {
        try {
          // The refresh endpoint returns a flat TokenPairOut ({ access, refresh, ... }).
          // `raw: true` keeps this call out of the client's 401 auto-refresh retry
          // (preventing an infinite refresh loop); we parse the JSON body ourselves.
          const response = await api.post('/auth/token/refresh', { refresh: this.refreshToken }, { raw: true })
          const res = await response.json()
          this.setTokens(res.access, res.refresh, res.access_expires_in)
        } finally {
          refreshPromise = null
        }
      })()
      return refreshPromise
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
      this.tokenExpiresAt = null
      localStorage.removeItem('fc_access')
      localStorage.removeItem('fc_refresh')
      localStorage.removeItem('fc_user')
      localStorage.removeItem('fc_access_expires')
    },
  },
})
