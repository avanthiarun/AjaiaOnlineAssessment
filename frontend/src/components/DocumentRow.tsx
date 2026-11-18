import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Link } from "react-router-dom";
import type { DocumentSummary } from "../api/client";
import { formatRelative } from "../utils/time";
import { DocIcon } from "./DocIcon";

interface Props {
  doc: DocumentSummary;
  shared?: boolean;
  /** Owned rows get a Rename/Delete menu. */
  onRename?: (title: string) => Promise<void>;
  onDelete?: () => Promise<void>;
}

export function DocumentRow({ doc, shared = false, onRename, onDelete }: Props) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [draft, setDraft] = useState(doc.title);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const close = (event: MouseEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) setMenuOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [menuOpen]);

  function startRename() {
    setMenuOpen(false);
    setDraft(doc.title);
    setRenaming(true);
  }

  async function finishRename() {
    if (!renaming) return;
    setRenaming(false);
    const title = draft.trim();
    if (title && title !== doc.title) await onRename?.(title);
  }

  function handleRenameKey(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") void finishRename();
    if (event.key === "Escape") setRenaming(false);
  }

  async function handleDelete() {
    setMenuOpen(false);
    if (window.confirm(`Delete "${doc.title}"? This cannot be undone.`)) await onDelete?.();
  }

  return (
    <li className="doc-row">
      {renaming ? (
        <div className="doc-row-main">
          <DocIcon />
          <input
            className="rename-input"
            aria-label="Document title"
            value={draft}
            maxLength={200}
            autoFocus
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={handleRenameKey}
            onBlur={() => void finishRename()}
          />
        </div>
      ) : (
        <Link to={`/d/${doc.id}`} className="doc-row-main">
          <DocIcon />
          <span className="doc-title">{doc.title}</span>
          {shared && <span className={`badge badge-${doc.role}`}>{doc.role === "editor" ? "Editor" : "Viewer"}</span>}
        </Link>
      )}
      {shared && <span className="doc-owner">{doc.owner.name}</span>}
      <span className="doc-time" title={new Date(doc.updated_at).toLocaleString()}>
        {formatRelative(doc.updated_at)}
      </span>
      {onRename && onDelete ? (
        <div className="menu" ref={menuRef}>
          <button
            className="icon-btn"
            aria-label={`More actions for ${doc.title}`}
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((open) => !open)}
          >
            ⋮
          </button>
          {menuOpen && (
            <div className="menu-list" role="menu" onKeyDown={(e) => e.key === "Escape" && setMenuOpen(false)}>
              <button role="menuitem" autoFocus onClick={startRename}>
                Rename
              </button>
              <button role="menuitem" className="danger" onClick={() => void handleDelete()}>
                Delete
              </button>
            </div>
          )}
        </div>
      ) : (
        <span className="menu-spacer" />
      )}
    </li>
  );
}
