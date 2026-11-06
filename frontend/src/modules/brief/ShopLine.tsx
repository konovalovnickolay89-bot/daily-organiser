type ShopLineProps = {
  name: string;
  ticked: boolean;
  busy?: boolean;
  onToggle: () => void;
};

export function ShopLine({ name, ticked, busy = false, onToggle }: ShopLineProps) {
  return (
    <label className="flex min-h-11 items-center gap-3 py-1">
      <input className="h-6 w-6 accent-accent" type="checkbox" checked={ticked} disabled={busy} aria-label={name} onChange={onToggle} />
      <span className={ticked ? "font-semibold text-success" : undefined}>{name}</span>
    </label>
  );
}
