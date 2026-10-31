import { STATUSES } from '../lib/labels'

export function StatusSelect({ task, onChange }) {
  return (
    <label className="inline-label">
      Status
      <select
        aria-label={`Status for ${task.title}`}
        value={task.status}
        onChange={(event) => onChange(task, event.target.value)}
      >
        {STATUSES.map((item) => (
          <option key={item.value} value={item.value}>
            {item.label}
          </option>
        ))}
      </select>
    </label>
  )
}
