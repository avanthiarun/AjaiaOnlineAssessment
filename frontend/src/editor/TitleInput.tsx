import { useState, type KeyboardEvent } from "react";
import { api, ApiError } from "../api/client";

interface Props {
  docId: string;
  initialTitle: string;
  canEdit: boolean;
  /** Called with the title once the server has saved it. */
  onRenamed: (title: string) => void;
  /** Called with a message to show (empty string clears it). */
  onError: (message: string) => void;
}

/** Inline document title: edit, then Enter or click away to rename; Escape cancels. */
export function TitleInput({ docId, initialTitle, canEdit, onRenamed, onError }: Props) {
  const [title, setTitle] = useState(initialTitle);
  const [saved, setSaved] = useState(initialTitle);

  async function save() {
    const next = title.trim();
    if (!next) {
      setTitle(saved);
      onError("Title can't be empty.");
      return;
    }
    setTitle(next);
    if (next === saved) return;
    try {
      await api.updateDocument(docId, { title: next });
      setSaved(next);
      onRenamed(next);
      onError("");
    } catch (err) {
      setTitle(saved);
      onError(err instanceof ApiError ? err.detail : "Couldn't rename the document.");
    }
  }

  function handleKey(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") event.currentTarget.blur();
    if (event.key === "Escape") {
      setTitle(saved);
      const input = event.currentTarget;
      setTimeout(() => input.blur()); // after React has applied the reset, so blur doesn't save
    }
  }

  return (
    <input
      className="title-input"
      aria-label="Document title"
      value={title}
      maxLength={200}
      readOnly={!canEdit}
      onChange={(e) => setTitle(e.target.value)}
      onBlur={() => canEdit && void save()}
      onKeyDown={handleKey}
    />
  );
}
