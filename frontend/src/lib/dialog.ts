import { useCallback, useEffect, useRef, type RefObject } from "react";

/**
 * Open a native dialog and put focus back on the control that opened it.
 * The opener is whatever was focused before showModal.
 */
export function useHouseDialog(onClose: () => void): {
  dialogRef: RefObject<HTMLDialogElement>;
  requestClose: () => void;
} {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  const requestClose = useCallback(() => {
    onCloseRef.current();
  }, []);

  useEffect(() => {
    const node = dialogRef.current;
    if (!node) return undefined;
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    node.showModal();

    function dismiss(event: Event) {
      event.preventDefault();
      onCloseRef.current();
    }

    function onClick(event: MouseEvent) {
      if (event.target === node) onCloseRef.current();
    }

    node.addEventListener("cancel", dismiss);
    node.addEventListener("click", onClick);
    return () => {
      node.removeEventListener("cancel", dismiss);
      node.removeEventListener("click", onClick);
      if (node.open) node.close();
      if (opener && opener.isConnected && !node.contains(opener)) opener.focus();
    };
  }, []);

  return { dialogRef, requestClose };
}
