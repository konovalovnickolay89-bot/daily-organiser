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

export function createTask({
  title,
  dueDate,
  priority,
  status,
  recurring,
  assistMode,
  contextHint,
}) {
  const body = {
    title,
    due_date: dueDate || null,
    priority,
    status,
    recurring: Boolean(recurring),
  }
  if (assistMode) body.assist_mode = assistMode
  const hint = (contextHint || '').trim()
  if (hint) body.context_hint = hint
  return request('/api/tasks', {
    method: 'POST',
    body: JSON.stringify(body),
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
