import { formatWhen } from '../lib/labels'
import { DeleteButton } from './DeleteButton'

export function NoteList({ notes, onDelete, empty }) {
  if (!notes.length) {
    return <p className="muted">{empty}</p>
  }
  return (
    <ul className="list">
      {notes.map((note) => (
        <li key={note.id} className={onDelete ? 'card note' : 'note'}>
          <p>{note.body}</p>
          <p className="muted">
            {formatWhen(note.created_at)}
            {note.tags.length ? ` · ${note.tags.join(', ')}` : ''}
            {note.task_title ? ` · ${note.task_title}` : ''}
            {note.source === 'bot' ? ' · Bot' : ''}
          </p>
          {onDelete ? <DeleteButton onDelete={() => onDelete(note)} /> : null}
        </li>
      ))}
    </ul>
  )
}
