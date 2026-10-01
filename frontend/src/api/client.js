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

/**
 * Upload a file (multipart/form-data) to the API.
 *
 * Unlike :func:`request`, this does not set a JSON content type; the browser
 * supplies the multipart boundary. Extra form fields can be passed as the
 * third argument.
 *
 * @param {string} path - API path (relative to /api/v1).
 * @param {File} file - The file to upload.
 * @param {Record<string, any>} fields - Optional extra form fields.
 * @returns {Promise<any>} The parsed JSON response.
 */
async function upload(path, file, fields = {}) {
  const auth = useAuthStore()
  const form = new FormData()
  form.append('file', file)
  for (const [key, value] of Object.entries(fields)) {
    if (value !== undefined && value !== null) form.append(key, value)
  }
  const headers = {}
  if (auth.accessToken) headers['Authorization'] = `Bearer ${auth.accessToken}`
  const res = await fetch(`${BASE}${path}`, { method: 'POST', headers, body: form })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || err.file?.[0] || `HTTP ${res.status}`)
  }
  return res.json()
}

/**
 * Download a file (e.g. the CSV import template) and trigger a browser save.
 *
 * @param {string} path - API path (relative to /api/v1).
 * @param {string} filename - Suggested file name for the download.
 */
async function download(path, filename) {
  const auth = useAuthStore()
  const headers = {}
  if (auth.accessToken) headers['Authorization'] = `Bearer ${auth.accessToken}`
  const res = await fetch(`${BASE}${path}`, { headers })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export const api = {
  get: (path) => request('GET', path),
  post: (path, body, opts) => request('POST', path, body, opts),
  put: (path, body) => request('PUT', path, body),
  delete: (path) => request('DELETE', path),
  upload: (path, file, fields) => upload(path, file, fields),
  download: (path, filename) => download(path, filename),
}
