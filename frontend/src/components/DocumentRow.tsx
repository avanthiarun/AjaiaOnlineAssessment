import { useCallback, useRef, useState, type KeyboardEvent } from "react";
import { Link } from "react-router-dom";
import type { DocumentSummary } from "../api/client";
import { ROLE_LABEL } from "../utils/roles";
import { formatRelative } from "../utils/time";
import { DocIcon } from "./DocIcon";
import { useDismiss } from "./useDismiss";

interface Props {
  doc: DocumentSummary;
  shared?: boolean;
  /** Owned rows get Rename/Delete; shared rows get Leave. The menu shows whichever are given. */
  onRename?: (title: string) => Promise<void>;
  onDelete?: () => Promise<void>;
  onLeave?: () => Promise<void>;
}

export function DocumentRow({ doc, shared = false, onRename, onDelete, onLeave }: Props) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [draft, setDraft] = useState(doc.title);
  const menuRef = useRef<HTMLDivElement>(null);
  const closeMenu = useCallback(() => setMenuOpen(false), []);
  useDismiss(menuRef, menuOpen, closeMenu);
  const hasMenu = Boolean(onRename || onDelete || onLeave);

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

  async function confirmThen(message: string, action?: () => Promise<void>) {
    setMenuOpen(false);
    if (window.confirm(message)) await action?.();
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
          {shared && <span className={`badge badge-${doc.role}`}>{ROLE_LABEL[doc.role]}</span>}
        </Link>
      )}
      <span className="doc-owner">{shared ? doc.owner.name : "me"}</span>
      <span className="doc-time" title={new Date(doc.updated_at).toLocaleString()}>
        {formatRelative(doc.updated_at)}
      </span>
      {hasMenu ? (
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
            <div className="menu-list" role="menu">
              {onRename && (
                <button role="menuitem" autoFocus onClick={startRename}>
                  Rename
                </button>
              )}
              {onDelete && (
                <button
                  role="menuitem"
                  className="danger"
                  onClick={() => void confirmThen(`Delete "${doc.title}"? This cannot be undone.`, onDelete)}
                >
                  Delete
                </button>
              )}
              {onLeave && (
                <button
                  role="menuitem"
                  autoFocus
                  className="danger"
                  onClick={() =>
                    void confirmThen(`Leave "${doc.title}"? You'll lose access until the owner shares it again.`, onLeave)
                  }
                >
                  Leave
                </button>
              )}
            </div>
          )}
        </div>
      ) : (
        <span className="menu-spacer" />
      )}
    </li>
  );
}
