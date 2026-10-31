import { request } from './client'

export function listTasks({ status, priority, due, q } = {}) {
  const params = new URLSearchParams()
  if (status) params.set('status', status)
  if (priority) params.set('priority', priority)
  if (due) params.set('due', due)
  if (q) params.set('q', q)
  const query = params.toString()
  return request(`/api/tasks${query ? `?${query}` : ''}`)
}

export function createTask({ title, dueDate, priority, status, recurring }) {
  return request('/api/tasks', {
    method: 'POST',
    body: JSON.stringify({
      title,
      due_date: dueDate || null,
      priority,
      status,
      recurring: Boolean(recurring),
    }),
  })
}

export function updateTask(id, patch) {
  return request(`/api/tasks/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  })
}

export function deleteTask(id) {
  return request(`/api/tasks/${id}`, { method: 'DELETE' })
}
