type RailProps = {
  view: string;
  onView: (view: string) => void;
};

const ITEMS = [
  { id: "home", label: "Home" },
  { id: "brief", label: "Brief" },
  { id: "tasks", label: "Tasks" },
  { id: "approvals", label: "Approvals" },
  { id: "today", label: "Today" },
  { id: "settings", label: "Settings", spaced: true },
];

function Icon({ name }: { name: string }) {
  const props = {
    viewBox: "0 0 24 24",
    "aria-hidden": true,
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.6,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    className: "block h-6 w-6",
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

export function Rail({ view, onView }: RailProps) {
  return (
    <nav
      className="rail sticky top-0 z-[4] flex h-screen w-rail shrink-0 flex-col items-center gap-2 border-r border-[var(--line-canvas)] bg-canvas px-0 pb-4 pt-4 max-[720px]:h-auto max-[720px]:w-full max-[720px]:flex-row max-[720px]:justify-between max-[720px]:border-b max-[720px]:border-r-0 max-[720px]:px-2 max-[720px]:py-2"
      aria-label="House"
    >
      {ITEMS.map((item) => (
        <span key={item.id} className={item.spaced ? "mt-auto flex max-[720px]:mt-0" : "flex"}>
          <button
            type="button"
            className="calm grid h-11 w-11 place-items-center rounded-rail border-0 bg-transparent p-0 text-accent hover:bg-[rgba(244,236,223,0.06)] hover:text-cream aria-[current=page]:bg-[var(--accent-soft)] aria-[current=page]:text-accent aria-[current=page]:hover:bg-[var(--accent-soft)] aria-[current=page]:hover:text-accent"
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
