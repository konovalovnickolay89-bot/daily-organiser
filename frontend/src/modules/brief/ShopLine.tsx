type ShopLineProps = {
  name: string;
  ticked: boolean;
  busy?: boolean;
  onToggle: () => void;
};

export function ShopLine({ name, ticked, busy = false, onToggle }: ShopLineProps) {
  return (
    <label className="shop-line">
      <input type="checkbox" checked={ticked} disabled={busy} aria-label={name} onChange={onToggle} />
      <span className={ticked ? "shop-name is-ticked" : "shop-name"}>{name}</span>
    </label>
  );
}
