import { useEffect, type RefObject } from "react";

const NEXT_KEYS: Record<string, (index: number, count: number) => number> = {
  ArrowDown: (i, n) => (i + 1) % n,
  ArrowUp: (i, n) => (i - 1 + n) % n,
  Home: () => 0,
  End: (_, n) => n - 1,
};

/**
 * Behaviour for a dropdown menu whose wrapper (`ref`) holds the trigger button followed by the list.
 * While `open`: a mouse press outside closes it; Escape closes it and returns focus to the trigger;
 * arrow keys / Home / End move between `role="menuitem"` entries (WAI-ARIA menu pattern).
 */
export function useDismiss(ref: RefObject<HTMLElement>, open: boolean, onClose: () => void) {
  useEffect(() => {
    if (!open) return;
    const onMouseDown = (event: MouseEvent) => {
      if (!ref.current?.contains(event.target as Node)) onClose();
    };
    const onKeyDown = (event: KeyboardEvent) => {
      const root = ref.current;
      if (event.key === "Escape") {
        const hadFocus = root?.contains(document.activeElement) ?? false;
        onClose();
        if (hadFocus) root?.querySelector<HTMLElement>("button")?.focus();
        return;
      }
      const next = NEXT_KEYS[event.key];
      if (!next || !root) return;
      const items = Array.from(root.querySelectorAll<HTMLElement>('[role="menuitem"]'));
      if (items.length === 0) return;
      event.preventDefault(); // don't scroll the page
      const current = items.indexOf(document.activeElement as HTMLElement);
      items[current === -1 ? 0 : next(current, items.length)].focus();
    };
    document.addEventListener("mousedown", onMouseDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onMouseDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [ref, open, onClose]);
}
