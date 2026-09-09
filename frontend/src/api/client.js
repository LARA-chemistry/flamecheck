import { useAuthStore } from '../stores/auth'

const BASE = '/api/v1'

async function request(method, path, body, opts = {}) {
  const auth = useAuthStore()
  const headers = { 'Content-Type': 'application/json' }
  if (auth.accessToken) {
    headers['Authorization'] = `Bearer ${auth.accessToken}`
  }

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })

  if (res.status === 401 && auth.refreshToken && !opts.raw) {
    await auth.refresh()
    headers['Authorization'] = `Bearer ${auth.accessToken}`
    const retry = await fetch(`${BASE}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    })
    if (!retry.ok) {
      throw new Error(`HTTP ${retry.status}`)
    }
    return retry.json()
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }

  if (opts.raw) return res
  return res.json()
}

export const api = {
  get: (path) => request('GET', path),
  post: (path, body, opts) => request('POST', path, body, opts),
  put: (path, body) => request('PUT', path, body),
  delete: (path) => request('DELETE', path),
}
