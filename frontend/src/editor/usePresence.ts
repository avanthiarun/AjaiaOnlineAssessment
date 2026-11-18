import { useEffect, useRef, useState } from "react";
import { api, type Presence } from "../api/client";

const HEARTBEAT_MS = 10_000;

/**
 * Heartbeat while the document is open (now, then every 10s), paused while the tab is hidden.
 * Returns the latest answer: who else is here and the document's current version.
 */
export function usePresence(docId: string, isEditing: () => boolean): Presence | null {
  const [presence, setPresence] = useState<Presence | null>(null);
  const isEditingRef = useRef(isEditing);
  isEditingRef.current = isEditing;

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setInterval> | undefined;
    const beat = () =>
      api
        .presence(docId, isEditingRef.current())
        .then((next) => active && setPresence(next))
        .catch(() => {}); // best effort: a missed heartbeat only delays the avatars
    const restart = () => {
      clearInterval(timer);
      if (document.hidden) return;
      void beat();
      timer = setInterval(() => void beat(), HEARTBEAT_MS);
    };
    restart();
    document.addEventListener("visibilitychange", restart);
    return () => {
      active = false;
      clearInterval(timer);
      document.removeEventListener("visibilitychange", restart);
    };
  }, [docId]);

  return presence;
}
