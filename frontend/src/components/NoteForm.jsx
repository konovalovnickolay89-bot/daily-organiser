export function NoteForm({
  idPrefix,
  body,
  tags,
  taskId = '',
  tasks = [],
  showTask = false,
  rows = 4,
  pending = false,
  submitLabel = 'Save note',
  onBody,
  onTags,
  onTaskId,
  onSubmit,
}) {
  return (
    <form className="stack-form" onSubmit={onSubmit} autoComplete="off">
      <label htmlFor={`${idPrefix}-body`}>Note</label>
      <textarea
        id={`${idPrefix}-body`}
        value={body}
        onChange={(event) => onBody(event.target.value)}
        rows={rows}
        required
      />
      <div className={showTask ? 'split' : undefined}>
        <div>
          <label htmlFor={`${idPrefix}-tags`}>Tags</label>
          <input
            id={`${idPrefix}-tags`}
            value={tags}
            onChange={(event) => onTags(event.target.value)}
            placeholder="home, errands"
          />
        </div>
        {showTask ? (
          <div>
            <label htmlFor={`${idPrefix}-task`}>Linked task</label>
            <select
              id={`${idPrefix}-task`}
              value={taskId}
              onChange={(event) => onTaskId(event.target.value)}
            >
              <option value="">None</option>
              {tasks.map((task) => (
                <option key={task.id} value={task.id}>
                  {task.title}
                </option>
              ))}
            </select>
          </div>
        ) : null}
      </div>
      <button type="submit" className="button button-primary" disabled={pending}>
        {pending ? 'Saving…' : submitLabel}
      </button>
    </form>
  )
}
