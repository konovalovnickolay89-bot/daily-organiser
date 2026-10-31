import { formatDate, priorityLabel, statusLabel } from '../lib/labels'
import { DeleteButton } from './DeleteButton'
import { StatusSelect } from './StatusSelect'

function taskExtras(task) {
  const bits = []
  if (task.source === 'bot') bits.push('Bot')
  if (task.assist_mode === 'off') bits.push('Assist off')
  if (task.context_hint) bits.push(task.context_hint)
  return bits
}

export function TaskList({ tasks, onStatus, onDelete, empty }) {
  if (!tasks.length) {
    return <p className="muted">{empty}</p>
  }
  return (
    <ul className="list">
      {tasks.map((task) => (
        <li key={task.id} className={onDelete ? 'row card' : 'row'} data-status={task.status}>
          <div>
            <p className="item-title">{task.title}</p>
            <p className="muted">
              {onDelete ? (
                <>
                  {formatDate(task.due_date)}
                  {' · '}
                  {priorityLabel(task.priority)}
                  {task.recurring ? ' · Repeats' : ''}
                  {taskExtras(task).length ? ` · ${taskExtras(task).join(' · ')}` : ''}
                </>
              ) : (
                <>
                  {priorityLabel(task.priority)}
                  {task.recurring ? ' · Repeats' : ''}
                  {taskExtras(task).length ? ` · ${taskExtras(task).join(' · ')}` : ''}
                  {' · '}
                  {statusLabel(task.status)}
                </>
              )}
            </p>
          </div>
          <div className="row-actions">
            <StatusSelect task={task} onChange={onStatus} />
            {onDelete ? <DeleteButton onDelete={() => onDelete(task)} /> : null}
          </div>
        </li>
      ))}
    </ul>
  )
}
