import { useState, type FormEvent } from "react";
import { addShoppingItem, tickShoppingItem, untickShoppingItem } from "../../api/shopping";
import { useHouse } from "../../house/HouseContext.jsx";
import { Disclosure } from "./Disclosure.jsx";
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
  const { refresh } = useHouse() as { refresh: () => void };
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
      className="brief-section"
      startOpen
      summary={
        <>
          <span className="chevron" aria-hidden="true" />
          <span className="section-title">Shopping</span>
          <span className="section-summary">{section.summary}</span>
        </>
      }
    >
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {section.items.length === 0 ? (
        <p className="empty">Shopping list is empty.</p>
      ) : (
        <ul className="item-list">
          {section.items.map((item) => (
            <li key={item.id ?? item.title} className="item">
              <ShopLine
                name={item.title}
                ticked={Boolean(item.ticked)}
                busy={busy}
                onToggle={() => void toggle(item)}
              />
            </li>
          ))}
        </ul>
      )}
      <form className="shop-add" onSubmit={(event) => void add(event)}>
        <label className="sr-only" htmlFor="shop-add">
          Add a shop item
        </label>
        <input
          id="shop-add"
          type="text"
          value={name}
          maxLength={80}
          autoComplete="off"
          placeholder="Oat milk"
          disabled={busy}
          onChange={(event) => setName(event.target.value)}
        />
        <button type="submit" className="primary" disabled={busy || name.trim() === ""}>
          Add
        </button>
      </form>
    </Disclosure>
  );
}
