import { PRIORITIES, STATUSES } from '../lib/labels'

export function TaskForm({ form, pending, onChange, onSubmit }) {
  return (
    <form className="card stack-form" onSubmit={onSubmit} autoComplete="off">
      <label htmlFor="task-title">Title</label>
      <input
        id="task-title"
        value={form.title}
        onChange={(event) => onChange('title', event.target.value)}
        maxLength={200}
        required
      />
      <div className="split">
        <div>
          <label htmlFor="task-due">Due date</label>
          <input
            id="task-due"
            type="date"
            value={form.due}
            onChange={(event) => onChange('due', event.target.value)}
          />
        </div>
        <div>
          <label htmlFor="task-priority">Priority</label>
          <select
            id="task-priority"
            value={form.priority}
            onChange={(event) => onChange('priority', event.target.value)}
          >
            {PRIORITIES.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="task-status">Status</label>
          <select
            id="task-status"
            value={form.status}
            onChange={(event) => onChange('status', event.target.value)}
          >
            {STATUSES.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </div>
      </div>
      <label className="check" htmlFor="task-recurring">
        <input
          id="task-recurring"
          type="checkbox"
          checked={form.recurring}
          onChange={(event) => onChange('recurring', event.target.checked)}
        />
        Repeats
      </label>
      <p className="hint">
        The repeat flag is stored for later. It does not create the next occurrence yet.
      </p>
      <details className="assist">
        <summary>Assist, optional</summary>
        <label htmlFor="task-assist">Assist</label>
        <select
          id="task-assist"
          value={form.assistMode}
          onChange={(event) => onChange('assistMode', event.target.value)}
        >
          <option value="when_useful">When useful</option>
          <option value="off">Off</option>
        </select>
        <label htmlFor="task-hint">Context hint</label>
        <input
          id="task-hint"
          value={form.contextHint}
          onChange={(event) => onChange('contextHint', event.target.value)}
          maxLength={300}
          placeholder="rota, or the train home"
        />
        <p className="hint">
          Leave this shut for a plain task. Nothing here runs a bot. A later routine can use the hint, and only change status or add a note after you say yes.
        </p>
      </details>
      <button type="submit" className="button button-primary" disabled={pending}>
        {pending ? 'Saving…' : 'Add task'}
      </button>
    </form>
  )
}
