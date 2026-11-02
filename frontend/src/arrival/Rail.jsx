const ITEMS = [
  { id: "home", label: "Home" },
  { id: "brief", label: "Brief" },
  { id: "tasks", label: "Tasks" },
  { id: "approvals", label: "Approvals" },
  { id: "today", label: "Today" },
  { id: "settings", label: "Settings", spaced: true },
];

function Icon({ name }) {
  const props = {
    viewBox: "0 0 24 24",
    "aria-hidden": true,
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.6,
    strokeLinecap: "round",
    strokeLinejoin: "round",
  };

  if (name === "home") {
    return (
      <svg {...props}>
        <path d="M4.5 11.2 12 5l7.5 6.2" />
        <path d="M7.2 10.6V19h9.6v-8.4" />
        <path d="M11 19v-3.2h2V19" />
      </svg>
    );
  }
  if (name === "brief") {
    return (
      <svg {...props}>
        <rect x="4" y="4" width="7" height="7" rx="1.2" />
        <rect x="13" y="4" width="7" height="7" rx="1.2" />
        <rect x="4" y="13" width="7" height="7" rx="1.2" />
        <rect x="13" y="13" width="7" height="7" rx="1.2" />
      </svg>
    );
  }
  if (name === "tasks") {
    return (
      <svg {...props}>
        <rect x="6" y="3.5" width="12" height="17" rx="1.5" />
        <path d="M9 8.5h6M9 12h6M9 15.5h4" />
      </svg>
    );
  }
  if (name === "approvals") {
    return (
      <svg {...props}>
        <path d="M12 3.5 19.5 6.2v5.2c0 4.3-3 7.3-7.5 8.8-4.5-1.5-7.5-4.5-7.5-8.8V6.2z" />
      </svg>
    );
  }
  if (name === "today") {
    return (
      <svg {...props}>
        <circle cx="12" cy="12" r="7.5" />
        <path d="M12 8.2V12l2.8 2" />
      </svg>
    );
  }
  return (
    <svg {...props}>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 4v2M12 18v2M4 12h2M18 12h2M6.3 6.3l1.4 1.4M16.3 16.3l1.4 1.4M17.7 6.3l-1.4 1.4M7.7 16.3l-1.4 1.4" />
    </svg>
  );
}

export function Rail({ view, onView }) {
  return (
    <nav className="rail" aria-label="House">
      {ITEMS.map((item) => (
        <span key={item.id} className={item.spaced ? "rail-slot rail-slot-end" : "rail-slot"}>
          <button
            type="button"
            className="rail-button"
            title={item.label}
            aria-current={view === item.id ? "page" : undefined}
            onClick={() => onView(item.id)}
          >
            <Icon name={item.id} />
            <span className="sr-only">{item.label}</span>
          </button>
        </span>
      ))}
    </nav>
  );
}
