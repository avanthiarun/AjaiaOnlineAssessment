import { EditorContent, useEditor } from "@tiptap/react";
import { useEffect, useRef, useState } from "react";
import { api, ApiError, type VersionDetail, type VersionSummary } from "../api/client";
import { formatRelative } from "../utils/time";
import { EDITOR_EXTENSIONS } from "./extensions";

interface Props {
  docId: string;
  canRestore: boolean;
  /** Called with the selected version's content (null when nothing is selected). */
  onPreview: (version: VersionDetail | null) => void;
  /** Restores the version; rejects with an ApiError if the server refuses. */
  onRestore: (versionId: string) => Promise<void>;
  onClose: () => void;
}

/** Right-side panel listing saved versions; selecting one previews it in the page area. */
export function VersionHistory({ docId, canRestore, onPreview, onRestore, onClose }: Props) {
  const [versions, setVersions] = useState<VersionSummary[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [restoring, setRestoring] = useState(false);
  const latestRequest = useRef<string | null>(null);

  useEffect(() => {
    api
      .listVersions(docId)
      .then(setVersions)
      .catch(() => setError("Couldn't load version history."));
  }, [docId]);

  async function select(id: string) {
    setSelected(id);
    setError("");
    latestRequest.current = id;
    try {
      const version = await api.getVersion(docId, id);
      if (latestRequest.current === id) onPreview(version); // ignore answers to earlier clicks
    } catch {
      if (latestRequest.current === id) setError("Couldn't load this version.");
    }
  }

  async function restore() {
    if (!selected) return;
    if (!window.confirm("Restore this version? The current text will be kept in version history.")) return;
    setRestoring(true);
    try {
      await onRestore(selected);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't restore this version.");
      setRestoring(false);
    }
  }

  return (
    <aside className="side-panel" aria-label="Version history">
      <div className="side-panel-header">
        <h2>Version history</h2>
        <button className="icon-btn" aria-label="Close version history" title="Close" onClick={onClose}>
          ×
        </button>
      </div>
      {error && (
        <p className="side-panel-error" role="alert">
          {error}
        </p>
      )}
      {versions === null ? (
        !error && <p className="side-panel-note">Loading…</p>
      ) : versions.length === 0 ? (
        <p className="side-panel-note">No earlier versions yet. One is saved at most every 5 minutes while editing.</p>
      ) : (
        <ul className="history-list">
          {versions.map((version) => (
            <li key={version.id}>
              <button
                className={version.id === selected ? "selected" : undefined}
                aria-pressed={version.id === selected}
                title={new Date(version.created_at).toLocaleString()}
                onClick={() => void select(version.id)}
              >
                <span className="history-time">{formatRelative(version.created_at)}</span>
                <span className="history-author">{version.created_by}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {selected && canRestore && (
        <button className="btn btn-primary history-restore" disabled={restoring} onClick={() => void restore()}>
          {restoring ? "Restoring…" : "Restore this version"}
        </button>
      )}
    </aside>
  );
}

/** Read-only rendering of a version, styled exactly like the editor. */
export function VersionPreview({ html }: { html: string }) {
  const editor = useEditor({ extensions: EDITOR_EXTENSIONS, content: html, editable: false });
  return (
    <article className="doc-page" aria-label="Version preview">
      <EditorContent editor={editor} />
    </article>
  );
}
