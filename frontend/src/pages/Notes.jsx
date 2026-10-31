import { useCallback, useEffect, useState } from 'react'
import { createNote, deleteNote, listNotes, listTasks } from '../api'
import { ErrorText } from '../components/ErrorText'
import { NoteForm } from '../components/NoteForm'
import { NoteList } from '../components/NoteList'
import { visibleError } from '../lib/errors'

export function Notes() {
  const [notes, setNotes] = useState(null)
  const [tasks, setTasks] = useState([])
  const [body, setBody] = useState('')
  const [tags, setTags] = useState('')
  const [taskId, setTaskId] = useState('')
  const [q, setQ] = useState('')
  const [tag, setTag] = useState('')
  const [active, setActive] = useState({ q: '', tag: '' })
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)

  const load = useCallback(async (query) => {
    const [noteRows, taskRows] = await Promise.all([
      listNotes(query),
      listTasks(),
    ])
    setNotes(noteRows)
    setTasks(taskRows)
  }, [])

  useEffect(() => {
    let cancelled = false
    load(active).catch((err) => {
      if (!cancelled) setError(visibleError(err))
    })
    return () => {
      cancelled = true
    }
  }, [load, active])

  async function create(event) {
    event.preventDefault()
    setPending(true)
    setError('')
    try {
      await createNote({ body, tags, taskId })
      setBody('')
      setTags('')
      setTaskId('')
      await load(active)
    } catch (err) {
      setError(visibleError(err))
    } finally {
      setPending(false)
    }
  }

  async function remove(note) {
    setError('')
    try {
      await deleteNote(note.id)
      await load(active)
    } catch (err) {
      setError(visibleError(err))
    }
  }

  function search(event) {
    event.preventDefault()
    setActive({ q: q.trim(), tag: tag.trim() })
  }

  return (
    <div className="stack">
      <header className="page-head">
        <h2>Notes</h2>
        <p className="muted">Quick capture, tags, and an optional link to a task.</p>
      </header>
      <ErrorText>{error}</ErrorText>
      <div className="card">
        <NoteForm
          idPrefix="note"
          body={body}
          tags={tags}
          taskId={taskId}
          tasks={tasks}
          showTask
          pending={pending}
          onBody={setBody}
          onTags={setTags}
          onTaskId={setTaskId}
          onSubmit={create}
        />
      </div>
      <form className="toolbar" onSubmit={search}>
        <label htmlFor="note-search">Search</label>
        <input
          id="note-search"
          value={q}
          onChange={(event) => setQ(event.target.value)}
          placeholder="Words in the note"
        />
        <label htmlFor="note-tag-filter">Tag</label>
        <input
          id="note-tag-filter"
          value={tag}
          onChange={(event) => setTag(event.target.value)}
          placeholder="home"
        />
        <button type="submit" className="button">
          Search
        </button>
        <button
          type="button"
          className="button button-ghost"
          onClick={() => {
            setQ('')
            setTag('')
            setActive({ q: '', tag: '' })
          }}
        >
          Show all
        </button>
      </form>
      {notes === null ? (
        <p className="status-line">Loading notes…</p>
      ) : (
        <NoteList notes={notes} onDelete={remove} empty="No notes match." />
      )}
    </div>
  )
}
