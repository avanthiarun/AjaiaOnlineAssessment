import { useCallback, useRef, useState, type MouseEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { useDismiss } from "../components/useDismiss";

interface Props {
  docId: string;
  /** Sends pending edits, so downloads contain the latest text. */
  flush: () => Promise<void>;
  hasUnsaved: () => boolean;
  onVersionHistory: () => void;
  /** Present for shared users (owners can't leave their own document). */
  onLeave?: () => void;
  onError: (message: string) => void;
}

/** The Docs-style menu bar under the title. Only "File": the rest of Docs' menus have no features here. */
export function FileMenu({ docId, flush, hasUnsaved, onVersionHistory, onLeave, onError }: Props) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const close = useCallback(() => setOpen(false), []);
  useDismiss(ref, open, close);

  function choose(action: () => void) {
    setOpen(false);
    action();
  }

  async function newDocument() {
    try {
      const doc = await api.createDocument();
      navigate(`/d/${doc.id}`);
    } catch (err) {
      onError(err instanceof ApiError ? err.detail : "Couldn't create a document.");
    }
  }

  /** Export links download what the server has, so send pending edits first. */
  async function download(event: MouseEvent<HTMLAnchorElement>) {
    setOpen(false);
    if (!hasUnsaved()) return; // nothing pending: let the link download normally
    event.preventDefault();
    const href = event.currentTarget.href;
    await flush();
    window.location.assign(href); // Content-Disposition: attachment, so the page stays put
  }

  return (
    <nav className="menubar" aria-label="Document menu">
      <div className="menu" ref={ref}>
        <button
          className={`menubar-item${open ? " is-open" : ""}`}
          aria-haspopup="menu"
          aria-expanded={open}
          onClick={() => setOpen((value) => !value)}
        >
          File
        </button>
        {open && (
          <div className="menu-list menu-list-left" role="menu">
            <button role="menuitem" autoFocus onClick={() => choose(() => void newDocument())}>
              New document
            </button>
            <div className="menu-sep" role="separator" />
            <a role="menuitem" href={api.exportUrl(docId, "md")} download onClick={(e) => void download(e)}>
              Download as Markdown (.md)
            </a>
            <a role="menuitem" href={api.exportUrl(docId, "html")} download onClick={(e) => void download(e)}>
              Download as web page (.html)
            </a>
            <button role="menuitem" onClick={() => choose(() => window.print())}>
              Print or save as PDF <span className="menu-hint">Ctrl+P</span>
            </button>
            <div className="menu-sep" role="separator" />
            <button role="menuitem" onClick={() => choose(onVersionHistory)}>
              Version history
            </button>
            {onLeave && (
              <button role="menuitem" className="danger" onClick={() => choose(onLeave)}>
                Leave document
              </button>
            )}
          </div>
        )}
      </div>
    </nav>
  );
}
