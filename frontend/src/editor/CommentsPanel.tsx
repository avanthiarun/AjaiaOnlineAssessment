import { useCallback, useEffect, useState, type FormEvent, type KeyboardEvent } from "react";
import { api, ApiError, type Comment } from "../api/client";
import { formatRelative } from "../utils/time";

export const QUOTE_MAX_LENGTH = 500;
const BODY_MAX_LENGTH = 2000;

interface Props {
  docId: string;
  canComment: boolean;
  /** Text the new comment refers to; null when not composing ("" for a comment without a quote). */
  draftQuote: string | null;
  onDraftDone: () => void;
  onClose: () => void;
}

function message(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.detail : fallback;
}

/** Right-side panel: compose a comment on the selected text, and list open/resolved comments. */
export function CommentsPanel({ docId, canComment, draftQuote, onDraftDone, onClose }: Props) {
  const [comments, setComments] = useState<Comment[] | null>(null);
  const [showResolved, setShowResolved] = useState(false);
  const [body, setBody] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setComments(await api.listComments(docId));
    } catch (err) {
      setError(message(err, "Couldn't load comments."));
    }
  }, [docId]);

  useEffect(() => {
    void load();
  }, [load]);

  /** Run an API call, then (on success) `after`, then reload the list. */
  async function run(action: () => Promise<unknown>, fallback: string, after?: () => void) {
    setBusy(true);
    setError("");
    try {
      await action();
      after?.();
      await load();
    } catch (err) {
      setError(message(err, fallback));
    } finally {
      setBusy(false);
    }
  }

  async function submit(event?: FormEvent) {
    event?.preventDefault();
    if (!body.trim() || busy) return;
    // Close the box before the list reloads, so the text never shows in both places.
    await run(() => api.createComment(docId, { quote: draftQuote ?? "", body }), "Couldn't post the comment.", () => {
      setBody("");
      onDraftDone();
    });
  }

  function handleKey(event: KeyboardEvent<HTMLTextAreaElement>) {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") void submit();
    if (event.key === "Escape") onDraftDone();
  }

  function remove(comment: Comment) {
    if (!window.confirm("Delete this comment?")) return;
    void run(() => api.deleteComment(docId, comment.id), "Couldn't delete the comment.");
  }

  const open = comments?.filter((c) => !c.resolved) ?? [];
  const resolved = comments?.filter((c) => c.resolved) ?? [];
  const card = (comment: Comment) => (
    <CommentCard
      key={comment.id}
      comment={comment}
      busy={busy}
      onResolve={(next) => void run(() => api.setCommentResolved(docId, comment.id, next), "Couldn't update the comment.")}
      onDelete={() => remove(comment)}
    />
  );

  return (
    <aside className="side-panel" aria-label="Comments">
      <div className="side-panel-header">
        <h2>Comments</h2>
        <button className="icon-btn" aria-label="Close comments" title="Close" onClick={onClose}>
          ×
        </button>
      </div>

      {canComment && draftQuote !== null && (
        <form className="comment-composer" onSubmit={(e) => void submit(e)}>
          {draftQuote && <blockquote className="comment-quote">{draftQuote}</blockquote>}
          <textarea
            aria-label="Comment text"
            placeholder="Add a comment"
            value={body}
            maxLength={BODY_MAX_LENGTH}
            rows={3}
            autoFocus
            onChange={(e) => setBody(e.target.value)}
            onKeyDown={handleKey}
          />
          <div className="comment-composer-actions">
            <button type="button" className="btn" onClick={onDraftDone}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={busy || !body.trim()}>
              Comment
            </button>
          </div>
        </form>
      )}

      {error && (
        <p className="side-panel-error" role="alert">
          {error}
        </p>
      )}

      {comments === null ? (
        !error && <p className="side-panel-note">Loading…</p>
      ) : (
        <>
          {open.length === 0 ? (
            <p className="side-panel-note">
              No open comments.{canComment && " Select text and click Comment (Ctrl+Alt+M) to add one."}
            </p>
          ) : (
            <ul className="comment-list">{open.map(card)}</ul>
          )}
          {resolved.length > 0 && (
            <label className="comment-toggle">
              <input type="checkbox" checked={showResolved} onChange={(e) => setShowResolved(e.target.checked)} />
              Show resolved ({resolved.length})
            </label>
          )}
          {showResolved && resolved.length > 0 && <ul className="comment-list">{resolved.map(card)}</ul>}
        </>
      )}
    </aside>
  );
}

interface CardProps {
  comment: Comment;
  busy: boolean;
  onResolve: (resolved: boolean) => void;
  onDelete: () => void;
}

/** One comment. Quote and body are rendered as text (React escapes them), never as HTML. */
function CommentCard({ comment, busy, onResolve, onDelete }: CardProps) {
  return (
    <li className={`comment-card${comment.resolved ? " is-resolved" : ""}`}>
      <div className="comment-meta">
        <span className="comment-author">{comment.author.name}</span>
        <span className="muted small" title={new Date(comment.created_at).toLocaleString()}>
          {formatRelative(comment.created_at)}
        </span>
      </div>
      {comment.quote && <blockquote className="comment-quote">{comment.quote}</blockquote>}
      <p className="comment-body">{comment.body}</p>
      {(comment.can_resolve || comment.can_delete) && (
        <div className="comment-actions">
          {comment.can_resolve && (
            <button className="link-btn" disabled={busy} onClick={() => onResolve(!comment.resolved)}>
              {comment.resolved ? "Reopen" : "Resolve"}
            </button>
          )}
          {comment.can_delete && (
            <button className="link-btn danger" disabled={busy} onClick={onDelete}>
              Delete
            </button>
          )}
        </div>
      )}
    </li>
  );
}
