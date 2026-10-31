import { splitTagInput } from '../lib/tags'
import { request } from './client'

export function listNotes({ q, tag, taskId } = {}) {
  const params = new URLSearchParams()
  if (q) params.set('q', q)
  if (tag) params.set('tag', tag)
  if (taskId) params.set('task_id', String(taskId))
  const query = params.toString()
  return request(`/api/notes${query ? `?${query}` : ''}`)
}

export function createNote({ body, tags, taskId }) {
  return request('/api/notes', {
    method: 'POST',
    body: JSON.stringify({
      body,
      tags: splitTagInput(tags),
      task_id: taskId ? Number(taskId) : null,
    }),
  })
}

export function deleteNote(id) {
  return request(`/api/notes/${id}`, { method: 'DELETE' })
}
