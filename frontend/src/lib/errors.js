import { ApiError } from '../api/client'

export function visibleError(error) {
  if (error instanceof ApiError && error.status === 401) return ''
  return error?.message || 'Request failed'
}
