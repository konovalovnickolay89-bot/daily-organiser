// Same-origin API client. The house box serves this UI and FastAPI together.
// Leave VITE_API_BASE_URL empty so requests stay on that origin (or the Vite
// dev proxy). A non-empty value is only for a local override during development.

const API_BASE = String(import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

let onUnauthorized = () => {}

export function setUnauthorizedHandler(handler) {
  onUnauthorized = typeof handler === 'function' ? handler : () => {}
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

function detailMessage(data, fallback) {
  const detail = data && data.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) => item.msg || item.message || 'Invalid value')
      .join(' ')
  }
  return fallback || 'Request failed'
}

export async function request(path, options = {}) {
  const opts = {
    credentials: 'include',
    ...options,
  }
  if (opts.body != null) {
    opts.headers = {
      'Content-Type': 'application/json',
      ...(opts.headers || {}),
    }
  }

  const response = await fetch(`${API_BASE}${path}`, opts)
  if (response.status === 204) return null

  const text = await response.text()
  let data = null
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = null
    }
  }
  if (!response.ok) {
    if (response.status === 401 && path !== '/api/auth/login') {
      onUnauthorized()
    }
    throw new ApiError(detailMessage(data, response.statusText), response.status)
  }
  return data
}
