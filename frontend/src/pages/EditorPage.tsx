import Underline from "@tiptap/extension-underline";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, ApiError, type DocumentDetail } from "../api/client";
import { TopBar } from "../components/TopBar";
import { ShareDialog } from "../editor/ShareDialog";
import { Toolbar } from "../editor/Toolbar";
import { useAutosave, type SaveStatus } from "../editor/useAutosave";

const NOT_FOUND = "This document doesn't exist or you don't have access.";
const FORBIDDEN = "You no longer have permission to edit this document.";
const CONFLICT = "Someone else edited this document. Reload to see their changes.";
const CONFLICT_COPIED = `${CONFLICT} Your unsaved text is copied to the clipboard.`;

/** Turn access errors from a save into the same wording the rest of the app uses. */
function friendlySaveError(err: unknown): unknown {
  if (err instanceof ApiError && err.status === 404) return new ApiError(404, NOT_FOUND);
  if (err instanceof ApiError && err.status === 403) return new ApiError(403, FORBIDDEN);
  return err;
}

/** Loads the document, then hands it to the workspace (or shows a clear error). */
export function EditorPage() {
  const { id = "" } = useParams();
  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [error, setError] = useState("");
  const [loadCount, setLoadCount] = useState(0); // bumping it re-fetches and remounts the workspace

  useEffect(() => {
    setDoc(null);
    setError("");
    api
      .getDocument(id)
      .then(setDoc)
      .catch((err) => setError(err instanceof ApiError && err.status === 404 ? NOT_FOUND : "Could not open this document."));
  }, [id, loadCount]);

  if (error || !doc) {
    return (
      <>
        <TopBar />
        <main className="page-message">
          {error ? (
            <>
              <p>{error}</p>
              <Link to="/" className="btn">
                Back to documents
              </Link>
            </>
          ) : (
            "Loading…"
          )}
        </main>
      </>
    );
  }
  return <DocumentWorkspace key={`${doc.id}:${loadCount}`} doc={doc} onReload={() => setLoadCount((n) => n + 1)} />;
}

const STATUS_LABEL: Record<SaveStatus, string> = {
  saved: "All changes saved",
  saving: "Saving…",
  retrying: "Couldn't save, retrying",
  failed: "Couldn't save",
};

function DocumentWorkspace({ doc, onReload }: { doc: DocumentDetail; onReload: () => void }) {
  const navigate = useNavigate();
  const canEdit = doc.role !== "viewer";
  const isOwner = doc.role === "owner";

  const [title, setTitle] = useState(doc.title);
  const savedTitle = useRef(doc.title);
  const [titleError, setTitleError] = useState("");
  const [shareOpen, setShareOpen] = useState(false);
  const [conflict, setConflict] = useState<string | null>(null);
  // The version our content is based on; sent as base_version so stale saves get a 409.
  const version = useRef(doc.version);

  const autosave = useAutosave(async (html) => {
    try {
      const saved = await api.updateDocument(doc.id, { content_html: html, base_version: version.current });
      version.current = saved.version;
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) await reportConflict();
      throw friendlySaveError(err); // 409 is a 4xx, so the queue stops instead of retrying
    }
  });

  /** Save the user's text to the clipboard (best effort) before telling them to reload. */
  async function reportConflict() {
    let copied = false;
    try {
      await navigator.clipboard.writeText(editor?.getText() ?? "");
      copied = true;
    } catch {
      // Clipboard can be blocked (permissions, unfocused tab); the banner just won't promise a copy.
    }
    setConflict(copied ? CONFLICT_COPIED : CONFLICT);
  }
  const locked = !canEdit || autosave.status === "failed";

  const editor = useEditor({
    extensions: [StarterKit, Underline],
    content: doc.content_html,
    editable: canEdit,
    onUpdate: ({ editor }) => autosave.schedule(editor.getHTML()),
  });

  // Stop editing if the server starts refusing saves (e.g. access was revoked).
  // emitUpdate=false: toggling editability must not look like a content change (and trigger a save).
  useEffect(() => {
    editor?.setEditable(!locked, false);
  }, [editor, locked]);

  useEffect(() => {
    document.title = `${title || "Untitled document"} - Ajaia Docs`;
    return () => {
      document.title = "Ajaia Docs";
    };
  }, [title]);

  const { flush } = autosave;
  useEffect(() => {
    const saveShortcut = (event: globalThis.KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        void flush();
      }
    };
    window.addEventListener("keydown", saveShortcut);
    return () => window.removeEventListener("keydown", saveShortcut);
  }, [flush]);

  async function saveTitle() {
    const next = title.trim();
    if (!next) {
      setTitle(savedTitle.current);
      setTitleError("Title can't be empty.");
      return;
    }
    setTitle(next);
    if (next === savedTitle.current) return;
    try {
      await api.updateDocument(doc.id, { title: next });
      savedTitle.current = next;
      setTitleError("");
    } catch (err) {
      setTitle(savedTitle.current);
      setTitleError(err instanceof ApiError ? err.detail : "Couldn't rename the document.");
    }
  }

  function handleTitleKey(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") event.currentTarget.blur();
    if (event.key === "Escape") {
      setTitle(savedTitle.current);
      setTimeout(() => (event.target as HTMLInputElement).blur());
    }
  }

  async function goHome() {
    await autosave.flush();
    if (autosave.hasUnsaved() && !window.confirm("Some changes haven't been saved yet. Leave anyway?")) return;
    navigate("/");
  }

  const saveError = autosave.status === "failed" ? autosave.error : "";

  return (
    <div className="editor-layout">
      <TopBar>
        <div className="editor-header">
          <button className="icon-btn" aria-label="Back to documents" title="Back to documents" onClick={() => void goHome()}>
            ←
          </button>
          <input
            className="title-input"
            aria-label="Document title"
            value={title}
            maxLength={200}
            readOnly={!canEdit}
            onChange={(e) => setTitle(e.target.value)}
            onBlur={() => canEdit && void saveTitle()}
            onKeyDown={handleTitleKey}
          />
          {canEdit ? (
            <span className={`save-status status-${autosave.status}`} role="status">
              {STATUS_LABEL[autosave.status]}
            </span>
          ) : (
            <span className="badge badge-viewer">View only</span>
          )}
          <span className="editor-header-spacer" />
          {isOwner && (
            <button className="btn btn-primary" onClick={() => setShareOpen(true)}>
              Share
            </button>
          )}
        </div>
      </TopBar>

      {editor && <Toolbar editor={editor} disabled={locked} />}

      {conflict ? (
        <div className="banner banner-error editor-banner" role="alert">
          <span>{conflict}</span>
          <button className="btn" onClick={onReload}>
            Reload
          </button>
        </div>
      ) : (
        (titleError || saveError) && (
          <div className="banner banner-error editor-banner" role="alert">
            {saveError ? `Couldn't save. ${saveError}` : titleError}
          </div>
        )
      )}

      <div className="page-scroll">
        <article className="doc-page">
          <EditorContent editor={editor} />
        </article>
      </div>

      {isOwner && <ShareDialog docId={doc.id} open={shareOpen} onClose={() => setShareOpen(false)} />}
    </div>
  );
}
