import { formatDate, priorityLabel, statusLabel } from '../lib/labels'
import { DeleteButton } from './DeleteButton'
import { StatusSelect } from './StatusSelect'

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
                </>
              ) : (
                <>
                  {priorityLabel(task.priority)}
                  {task.recurring ? ' · Repeats' : ''}
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
