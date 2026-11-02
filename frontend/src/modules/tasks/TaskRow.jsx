/**
 * A task row that opens the editor. The whole row is the control.
 */
export function TaskRow({ title, meta, detail, onOpen }) {
  const label = meta ? `Open ${title}. ${meta}` : `Open ${title}`;

  return (
    <li className="item">
      <button type="button" className="item-button" onClick={onOpen} aria-label={label}>
        <span className="item-copy">
          <span className="item-title">{title}</span>
          {meta && <span className="meta">{meta}</span>}
          {detail && <span className="item-detail">{detail}</span>}
        </span>
        <span className="item-affordance" aria-hidden="true">
          ›
        </span>
      </button>
    </li>
  );
}
