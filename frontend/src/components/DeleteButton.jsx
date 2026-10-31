import { useState } from 'react'

export function DeleteButton({ onDelete, label = 'Delete' }) {
  const [armed, setArmed] = useState(false)

  return (
    <button
      type="button"
      className="button button-danger"
      onClick={() => {
        if (!armed) {
          setArmed(true)
          return
        }
        onDelete()
      }}
      onBlur={() => setArmed(false)}
    >
      {armed ? 'Confirm' : label}
    </button>
  )
}
