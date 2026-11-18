import { EditorContent, useEditor } from "@tiptap/react";
import { useCallback, useEffect, useRef, useState, type KeyboardEvent, type MouseEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, ApiError, type ActiveViewer, type DocumentDetail, type VersionDetail } from "../api/client";
import { TopBar } from "../components/TopBar";
import { useDismiss } from "../components/useDismiss";
import { EDITOR_EXTENSIONS } from "../editor/extensions";
import { PresenceAvatars } from "../editor/PresenceAvatars";
import { ShareDialog } from "../editor/ShareDialog";
import { Toolbar } from "../editor/Toolbar";
import { useAutosave, type SaveStatus } from "../editor/useAutosave";
import { usePresence } from "../editor/usePresence";
import { VersionHistory, VersionPreview } from "../editor/VersionHistory";
import { CommentsPanel, QUOTE_MAX_LENGTH } from "../editor/CommentsPanel";
import { canCommentRole, canEditRole, ROLE_LABEL } from "../utils/roles";

const NOT_FOUND = "This document doesn't exist or you don't have access.";
const FORBIDDEN = "You no longer have permission to edit this document.";
const CONFLICT = "Someone else edited this document. Reload to see their changes.";
const CONFLICT_COPIED = `${CONFLICT} Your unsaved text is copied to the clipboard.`;
const EDITING_WINDOW_MS = 15_000;

/** Best guess at who saved the newer version: the one person currently typing, if there is one. */
function whoUpdated(viewers: ActiveViewer[]): string {
  const typing = viewers.filter((viewer) => viewer.is_editing);
  return typing.length === 1 ? typing[0].name : "Someone";
}

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
  const canEdit = canEditRole(doc.role);
  const canComment = canCommentRole(doc.role);
  const isOwner = doc.role === "owner";

  const [title, setTitle] = useState(doc.title);
  const savedTitle = useRef(doc.title);
  const [headerError, setHeaderError] = useState("");
  const [shareOpen, setShareOpen] = useState(false);
  const [panel, setPanel] = useState<"history" | "comments" | null>(null); // one side panel at a time
  const [preview, setPreview] = useState<VersionDetail | null>(null);
  const [commentDraft, setCommentDraft] = useState<string | null>(null);
  const [downloadOpen, setDownloadOpen] = useState(false);
  const downloadRef = useRef<HTMLDivElement>(null);
  const closeDownload = useCallback(() => setDownloadOpen(false), []);
  useDismiss(downloadRef, downloadOpen, closeDownload);
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
  // While previewing a version the editor is hidden, so the toolbar must not change it.
  const locked = !canEdit || autosave.status === "failed" || preview !== null;
  const lastTypedAt = useRef(0);

  const editor = useEditor({
    extensions: EDITOR_EXTENSIONS,
    content: doc.content_html,
    editable: canEdit,
    onUpdate: ({ editor }) => {
      lastTypedAt.current = Date.now();
      autosave.schedule(editor.getHTML());
    },
  });

  const presence = usePresence(doc.id, () => canEdit && Date.now() - lastTypedAt.current < EDITING_WINDOW_MS);
  // Set when the server has a newer version and we have nothing unsaved to lose by reloading.
  const [updatedBy, setUpdatedBy] = useState<string | null>(null);
  const { hasUnsaved } = autosave;
  useEffect(() => {
    if (presence && presence.version > version.current && !hasUnsaved()) setUpdatedBy(whoUpdated(presence.viewers));
  }, [presence, hasUnsaved]);

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
  const startCommentRef = useRef(startComment);
  startCommentRef.current = startComment;
  useEffect(() => {
    const shortcuts = (event: globalThis.KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey)) return;
      if (event.key.toLowerCase() === "s") {
        event.preventDefault();
        void flush();
      } else if (event.altKey && event.code === "KeyM") {
        event.preventDefault(); // code, not key: Alt changes the character on some layouts
        startCommentRef.current();
      }
    };
    window.addEventListener("keydown", shortcuts);
    return () => window.removeEventListener("keydown", shortcuts);
  }, [flush]);

  async function saveTitle() {
    const next = title.trim();
    if (!next) {
      setTitle(savedTitle.current);
      setHeaderError("Title can't be empty.");
      return;
    }
    setTitle(next);
    if (next === savedTitle.current) return;
    try {
      await api.updateDocument(doc.id, { title: next });
      savedTitle.current = next;
      setHeaderError("");
    } catch (err) {
      setTitle(savedTitle.current);
      setHeaderError(err instanceof ApiError ? err.detail : "Couldn't rename the document.");
    }
  }

  function handleTitleKey(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") event.currentTarget.blur();
    if (event.key === "Escape") {
      setTitle(savedTitle.current);
      setTimeout(() => (event.target as HTMLInputElement).blur());
    }
  }

  /** Export links download what the server has, so send any pending edits first. */
  async function download(event: MouseEvent<HTMLAnchorElement>) {
    setDownloadOpen(false);
    if (!autosave.hasUnsaved()) return; // nothing pending: let the link download normally
    event.preventDefault();
    const href = event.currentTarget.href;
    await autosave.flush();
    window.location.assign(href); // Content-Disposition: attachment, so this downloads in place
  }

  function printPdf() {
    setDownloadOpen(false);
    window.print();
  }

  async function leave() {
    if (!window.confirm(`Leave "${title}"? You'll lose access until the owner shares it again.`)) return;
    await autosave.flush();
    try {
      await api.leaveDocument(doc.id);
      navigate("/");
    } catch (err) {
      setHeaderError(err instanceof ApiError ? err.detail : "Couldn't leave the document.");
    }
  }

  function openPanel(next: "history" | "comments" | null) {
    setPanel(next);
    setPreview(null);
    setCommentDraft(null);
  }

  /** Open the comment box for the text selected in the document (works for read-only roles too). */
  function startComment() {
    if (!canComment || !editor) return;
    const selection = window.getSelection();
    const inDocument = selection !== null && editor.view.dom.contains(selection.anchorNode);
    const quote = inDocument ? selection.toString().replace(/\s+/g, " ").trim().slice(0, QUOTE_MAX_LENGTH) : "";
    openPanel("comments");
    setCommentDraft(quote);
  }

  /** Save pending edits (so they land in history too), restore, then load the result. */
  async function restoreVersion(versionId: string) {
    await autosave.flush();
    await api.restoreVersion(doc.id, versionId);
    onReload();
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
            <span className={`badge badge-${doc.role}`}>
              {doc.role === "commenter" ? ROLE_LABEL.commenter : "View only"}
            </span>
          )}
          <span className="editor-header-spacer" />
          <PresenceAvatars viewers={presence?.viewers ?? []} />
          <button
            className="btn"
            aria-pressed={panel === "comments"}
            onClick={() => openPanel(panel === "comments" ? null : "comments")}
          >
            Comments
          </button>
          <button
            className="btn"
            aria-pressed={panel === "history"}
            onClick={() => openPanel(panel === "history" ? null : "history")}
          >
            Version history
          </button>
          <div className="menu" ref={downloadRef}>
            <button
              className="btn"
              aria-haspopup="menu"
              aria-expanded={downloadOpen}
              onClick={() => setDownloadOpen((open) => !open)}
            >
              Download
            </button>
            {downloadOpen && (
              <div className="menu-list" role="menu">
                <a role="menuitem" href={api.exportUrl(doc.id, "md")} download onClick={(e) => void download(e)}>
                  Markdown (.md)
                </a>
                <a role="menuitem" href={api.exportUrl(doc.id, "html")} download onClick={(e) => void download(e)}>
                  Web page (.html)
                </a>
                <button role="menuitem" onClick={printPdf}>
                  PDF (print)
                </button>
              </div>
            )}
          </div>
          {!isOwner && (
            <button className="btn" onClick={() => void leave()}>
              Leave
            </button>
          )}
          {isOwner && (
            <button className="btn btn-primary" onClick={() => setShareOpen(true)}>
              Share
            </button>
          )}
        </div>
      </TopBar>

      {editor && <Toolbar editor={editor} disabled={locked} onComment={canComment ? startComment : undefined} />}

      {conflict ? (
        <div className="banner banner-error editor-banner" role="alert">
          <span>{conflict}</span>
          <button className="btn" onClick={onReload}>
            Reload
          </button>
        </div>
      ) : updatedBy ? (
        <div className="banner banner-info editor-banner" role="status">
          <span>{updatedBy} updated this document</span>
          <button className="btn" onClick={onReload}>
            Reload
          </button>
        </div>
      ) : (
        (headerError || saveError) && (
          <div className="banner banner-error editor-banner" role="alert">
            {saveError ? `Couldn't save. ${saveError}` : headerError}
          </div>
        )
      )}

      <div className="editor-body">
        <div className="page-scroll">
          {preview && <VersionPreview key={preview.id} html={preview.content_html} />}
          <article className="doc-page" hidden={preview !== null}>
            <EditorContent editor={editor} />
          </article>
        </div>
        {panel === "history" && (
          <VersionHistory
            docId={doc.id}
            canRestore={canEdit}
            onPreview={setPreview}
            onRestore={restoreVersion}
            onClose={() => openPanel(null)}
          />
        )}
        {panel === "comments" && (
          <CommentsPanel
            docId={doc.id}
            canComment={canComment}
            draftQuote={commentDraft}
            onDraftDone={() => setCommentDraft(null)}
            onClose={() => openPanel(null)}
          />
        )}
      </div>

      {isOwner && (
        <ShareDialog docId={doc.id} open={shareOpen} onClose={() => setShareOpen(false)} onTransferred={onReload} />
      )}
    </div>
  );
}
