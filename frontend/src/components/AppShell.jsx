const VIEWS = [
  { id: 'today', label: 'Today' },
  { id: 'tasks', label: 'Tasks' },
  { id: 'notes', label: 'Notes' },
]

export function AppShell({ view, onNavigate, onLogout, children }) {
  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <span className="mark" aria-hidden="true">
            Do
          </span>
          <div>
            <p className="brand-name">Daily Organiser</p>
            <p className="brand-sub">Home</p>
          </div>
        </div>
        <nav className="nav" aria-label="Sections">
          {VIEWS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={view === item.id ? 'nav-button is-active' : 'nav-button'}
              aria-current={view === item.id ? 'page' : undefined}
              onClick={() => onNavigate(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <button type="button" className="button button-ghost logout" onClick={onLogout}>
          Log out
        </button>
      </header>
      <main className="content">{children}</main>
    </div>
  )
}
