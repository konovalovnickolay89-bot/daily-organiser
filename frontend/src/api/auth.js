import { request } from './client'

export function login(password) {
  return request('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ password }),
  })
}

export function logout() {
  return request('/api/auth/logout', { method: 'POST' })
}

export function currentSession() {
  return request('/api/auth/me')
}
