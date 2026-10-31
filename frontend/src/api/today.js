import { request } from './client'

export function getToday() {
  return request('/api/today')
}
