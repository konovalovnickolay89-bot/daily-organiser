import { useEffect, useState } from 'react'
import { createNote, createTask, getToday, updateTask } from '../api'
import { ErrorText } from '../components/ErrorText'
import { NoteForm } from '../components/NoteForm'
import { NoteList } from '../components/NoteList'
import { TaskList } from '../components/TaskList'
import { visibleError } from '../lib/errors'
import { PRIORITIES, formatDate } from '../lib/labels'

export function Today() {
  const [page, setPage] = useState(null)
  const [error, setError] = useState('')
  const [title, setTitle] = useState('')
  const [priority, setPriority] = useState('medium')
  const [note, setNote] = useState('')
  const [tags, setTags] = useState('')
  const [pending, setPending] = useState(false)

  async function load() {
    setPage(await getToday())
  }

  useEffect(() => {
    let cancelled = false
    getToday()
      .then((data) => {
        if (!cancelled) setPage(data)
      })
      .catch((err) => {
        if (!cancelled) setError(visibleError(err))
      })
    return () => {
      cancelled = true
    }
  }, [])

  async function addTask(event) {
    event.preventDefault()
    if (!page) return
    setPending(true)
    setError('')
    try {
      await createTask({
        title,
        dueDate: page.date,
        priority,
        status: 'todo',
        recurring: false,
      })
      setTitle('')
      await load()
    } catch (err) {
      setError(visibleError(err))
    } finally {
      setPending(false)
    }
  }

  async function addNote(event) {
    event.preventDefault()
    setPending(true)
    setError('')
    try {
      await createNote({ body: note, tags })
      setNote('')
      setTags('')
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

  if (!page) {
    return <p className="status-line">Loading today…</p>
  }

  return (
    <div className="stack">
      <header className="page-head">
        <h2>Today</h2>
        <p className="muted">{formatDate(page.date)}. This is the server's local date.</p>
      </header>
      <ErrorText>{error}</ErrorText>

      <section className="card">
        <h3>Add a task for today</h3>
        <form className="stack-form" onSubmit={addTask} autoComplete="off">
          <label htmlFor="today-task">Task</label>
          <input
            id="today-task"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            maxLength={200}
            required
          />
          <label htmlFor="today-priority">Priority</label>
          <select
            id="today-priority"
            value={priority}
            onChange={(event) => setPriority(event.target.value)}
          >
            {PRIORITIES.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
          <button type="submit" className="button button-primary" disabled={pending}>
            Add to today
          </button>
        </form>
        <TaskList
          tasks={page.tasks}
          onStatus={changeStatus}
          empty="Nothing due today."
        />
      </section>

      <section className="card">
        <h3>Capture a note</h3>
        <NoteForm
          idPrefix="today-note"
          body={note}
          tags={tags}
          rows={3}
          pending={pending}
          onBody={setNote}
          onTags={setTags}
          onSubmit={addNote}
        />
        <NoteList notes={page.notes} empty="No notes yet." />
      </section>
    </div>
  )
}
