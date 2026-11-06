import { useState, type FormEvent } from "react";
import { addShoppingItem, tickShoppingItem, untickShoppingItem } from "../../api/shopping";
import { cx, errorText, fieldInput, primary } from "../../arrival/ui";
import { EmptyState } from "../../components/EmptyState";
import { useHouse } from "../../house/HouseContext";
import { Chevron, Disclosure } from "./Disclosure";
import { ShopLine } from "./ShopLine";

type ShoppingItem = {
  id?: string | null;
  title: string;
  ticked?: boolean | null;
};

type ShoppingSection = {
  summary: string;
  items: ShoppingItem[];
};

export function ShoppingList({ section }: { section: ShoppingSection }) {
  const { refresh } = useHouse();
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function add(event: FormEvent) {
    event.preventDefault();
    const value = name.trim();
    if (!value || busy) return;
    setBusy(true);
    setError(null);
    try {
      await addShoppingItem(value);
      setName("");
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "The list did not update.");
    } finally {
      setBusy(false);
    }
  }

  async function toggle(item: ShoppingItem) {
    if (!item.id || busy) return;
    setBusy(true);
    setError(null);
    try {
      if (item.ticked) await untickShoppingItem(item.id);
      else await tickShoppingItem(item.id);
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "The list did not update.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Disclosure
      className="border-t border-[var(--line)] py-4"
      startOpen
      summary={
        <span className="flex min-h-11 flex-wrap items-baseline gap-2">
          <Chevron />
          <span className="font-semibold tracking-[-0.011em] text-[var(--ink)]">Shopping</span>
          <span
            className={cx(
              "ml-auto text-right text-sm font-normal text-[var(--muted)] max-[720px]:ml-4 max-[720px]:basis-full max-[720px]:text-left",
              /\d/.test(section.summary) && "font-mono tabular-nums",
            )}
          >
            {section.summary}
          </span>
        </span>
      }
    >
      {error && (
        <p className={errorText} role="alert">
          {error}
        </p>
      )}
      {section.items.length === 0 ? (
        <EmptyState>Shopping list is empty.</EmptyState>
      ) : (
        <ul className="m-0 mt-2 list-none p-0">
          {section.items.map((item) => (
            <li key={item.id ?? item.title}>
              <ShopLine name={item.title} ticked={Boolean(item.ticked)} busy={busy} onToggle={() => void toggle(item)} />
            </li>
          ))}
        </ul>
      )}
      <form className="mt-4 flex gap-2" onSubmit={(event) => void add(event)}>
        <label className="sr-only" htmlFor="shop-add">
          Add a shop item
        </label>
        <input
          id="shop-add"
          className={`${fieldInput} min-w-0 flex-1`}
          type="text"
          value={name}
          maxLength={80}
          autoComplete="off"
          placeholder="Oat milk"
          disabled={busy}
          onChange={(event) => setName(event.target.value)}
        />
        <button type="submit" className={`${primary} shrink-0`} disabled={busy || name.trim() === ""}>
          Add
        </button>
      </form>
    </Disclosure>
  );
}
