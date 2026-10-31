import { useCallback, useEffect, useState } from 'react'
import { createTask, deleteTask, getToday, listTasks, updateTask } from '../api'
import { ErrorText } from '../components/ErrorText'
import { TaskForm } from '../components/TaskForm'
import { TaskList } from '../components/TaskList'
import { visibleError } from '../lib/errors'
import { STATUSES } from '../lib/labels'

const EMPTY = {
  title: '',
  due: '',
  priority: 'medium',
  status: 'todo',
  recurring: false,
  assistMode: 'when_useful',
  contextHint: '',
}

export function Tasks() {
  const [tasks, setTasks] = useState(null)
  const [filter, setFilter] = useState('')
  const [form, setForm] = useState(EMPTY)
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)

  const load = useCallback(async () => {
    setTasks(await listTasks({ status: filter }))
  }, [filter])

  useEffect(() => {
    let cancelled = false
    load().catch((err) => {
      if (!cancelled) setError(visibleError(err))
    })
    return () => {
      cancelled = true
    }
  }, [load])

  useEffect(() => {
    let cancelled = false
    getToday()
      .then((data) => {
        if (!cancelled) {
          setForm((current) => (current.due ? current : { ...current, due: data.date }))
        }
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  async function create(event) {
    event.preventDefault()
    setPending(true)
    setError('')
    try {
      await createTask({
        title: form.title,
        dueDate: form.due,
        priority: form.priority,
        status: form.status,
        recurring: form.recurring,
        assistMode: form.assistMode,
        contextHint: form.contextHint,
      })
      setForm((current) => ({ ...EMPTY, due: current.due }))
      await load()
    } catch (err) {
      setError(visibleError(err))
    } finally {
      setPending(false)
    }
  }

  async function changeStatus(task, status) {
    setError('')
    try {
      await updateTask(task.id, { status })
      await load()
    } catch (err) {
      setError(visibleError(err))
    }
  }

  async function remove(task) {
    setError('')
    try {
      await deleteTask(task.id)
      await load()
    } catch (err) {
      setError(visibleError(err))
    }
  }

  return (
    <div className="stack">
      <header className="page-head">
        <h2>Tasks</h2>
        <p className="muted">A title is enough. Assist stays optional.</p>
      </header>
      <ErrorText>{error}</ErrorText>
      <TaskForm form={form} pending={pending} onChange={update} onSubmit={create} />
      <div className="toolbar">
        <label htmlFor="task-filter">Show</label>
        <select
          id="task-filter"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
        >
          <option value="">All</option>
          {STATUSES.map((item) => (
            <option key={item.value} value={item.value}>
              {item.label}
            </option>
          ))}
        </select>
      </div>
      {tasks === null ? (
        <p className="status-line">Loading tasks…</p>
      ) : (
        <TaskList
          tasks={tasks}
          onStatus={changeStatus}
          onDelete={remove}
          empty="No tasks in this list."
        />
      )}
    </div>
  )
}
