import { useEffect, useRef, useState } from "react";
import { ApiError } from "../api/client";

export type SaveStatus = "saved" | "saving" | "retrying" | "failed";

const RETRY_MS = 3000;

/** 4xx errors (other than timeout / rate limit) will not fix themselves, so we stop retrying. */
function isPermanent(err: unknown): err is ApiError {
  return err instanceof ApiError && err.status >= 400 && err.status < 500 && ![408, 429].includes(err.status);
}

export interface SaveQueue {
  schedule: (html: string) => void;
  flush: () => Promise<void>;
  hasUnsaved: () => boolean;
}

/**
 * Debounced, strictly sequential saving: at most one request in flight, and only the
 * latest content is sent next (intermediate edits are skipped, never sent out of order).
 */
export function createSaveQueue(
  save: (html: string) => Promise<void>,
  delayMs: number,
  onStatus: (status: SaveStatus, error?: string) => void,
): SaveQueue {
  let pending: string | null = null;
  let running: Promise<void> | null = null;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let stopped = false;

  async function drain(): Promise<void> {
    while (pending !== null && !stopped) {
      const html = pending;
      pending = null;
      onStatus("saving");
      try {
        await save(html);
      } catch (err) {
        pending ??= html; // keep it unless newer content arrived meanwhile
        if (isPermanent(err)) {
          stopped = true;
          onStatus("failed", err.detail);
        } else {
          onStatus("retrying");
          timer = setTimeout(() => void flush(), RETRY_MS);
        }
        return;
      }
    }
    if (!stopped) onStatus("saved");
  }

  function flush(): Promise<void> {
    clearTimeout(timer);
    running ??= drain().finally(() => {
      running = null;
    });
    return running;
  }

  return {
    schedule(html) {
      if (stopped) return;
      pending = html;
      onStatus("saving");
      clearTimeout(timer);
      timer = setTimeout(() => void flush(), delayMs);
    },
    flush,
    hasUnsaved: () => pending !== null || running !== null,
  };
}

/** React wrapper: exposes status and keeps one queue for the component's lifetime. */
export function useAutosave(save: (html: string) => Promise<void>, delayMs = 800) {
  const [status, setStatus] = useState<SaveStatus>("saved");
  const [error, setError] = useState("");
  const saveRef = useRef(save);
  saveRef.current = save;

  const queueRef = useRef<SaveQueue | null>(null);
  queueRef.current ??= createSaveQueue(
    (html) => saveRef.current(html),
    delayMs,
    (next, message = "") => {
      setStatus(next);
      setError(message);
    },
  );
  const queue = queueRef.current;

  useEffect(() => {
    const warnIfUnsaved = (event: BeforeUnloadEvent) => {
      if (!queue.hasUnsaved()) return;
      event.preventDefault();
      event.returnValue = ""; // required by some browsers to show the prompt
    };
    window.addEventListener("beforeunload", warnIfUnsaved);
    return () => {
      window.removeEventListener("beforeunload", warnIfUnsaved);
      void queue.flush(); // leaving the page in-app: send whatever is pending
    };
  }, [queue]);

  return { status, error, schedule: queue.schedule, flush: queue.flush, hasUnsaved: queue.hasUnsaved };
}
