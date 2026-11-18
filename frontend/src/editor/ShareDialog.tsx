import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError, type DemoUser, type ShareList, type ShareRole } from "../api/client";

interface Props {
  docId: string;
  open: boolean;
  onClose: () => void;
}

function message(err: unknown): string {
  return err instanceof ApiError ? err.detail : "Something went wrong. Please try again.";
}

/** Owner-only modal: add people by email and manage their roles. */
export function ShareDialog({ docId, open, onClose }: Props) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [access, setAccess] = useState<ShareList | null>(null);
  const [demoUsers, setDemoUsers] = useState<DemoUser[]>([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<ShareRole>("viewer");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    try {
      setAccess(await api.listShares(docId));
    } catch (err) {
      setError(message(err));
    }
  }, [docId]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      dialog.showModal();
      setError("");
      void reload();
      api.demoUsers().then(setDemoUsers).catch(() => setDemoUsers([]));
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open, reload]);

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await action();
      await reload();
    } catch (err) {
      setError(message(err));
    } finally {
      setBusy(false);
    }
  }

  function handleShare(event: FormEvent) {
    event.preventDefault();
    void run(async () => {
      await api.addShare(docId, email, role);
      setEmail("");
    });
  }

  return (
    <dialog ref={dialogRef} className="share-dialog" aria-labelledby="share-title" onClose={onClose}>
      <div className="share-header">
        <h2 id="share-title">Share document</h2>
        <button className="icon-btn" aria-label="Close" onClick={onClose}>
          ✕
        </button>
      </div>

      <form className="share-form" onSubmit={handleShare}>
        <input
          type="email"
          placeholder="Add people by email"
          aria-label="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoFocus
        />
        <select aria-label="Role" value={role} onChange={(e) => setRole(e.target.value as ShareRole)}>
          <option value="viewer">Viewer</option>
          <option value="editor">Editor</option>
        </select>
        <button className="btn btn-primary" type="submit" disabled={busy || !email.trim()}>
          Share
        </button>
      </form>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {demoUsers.length > 0 && (
        <p className="muted small share-hint">Demo accounts: {demoUsers.map((u) => u.email).join(", ")}</p>
      )}

      <h3 className="share-subtitle">People with access</h3>
      {access === null ? (
        <p className="muted">Loading…</p>
      ) : (
        <ul className="people">
          <li>
            <Person name={access.owner.name} email={access.owner.email} />
            <span className="muted">Owner</span>
          </li>
          {access.shares.map((share) => (
            <li key={share.user.id}>
              <Person name={share.user.name} email={share.user.email} />
              <select
                aria-label={`Role for ${share.user.name}`}
                value={share.role}
                disabled={busy}
                onChange={(e) => void run(() => api.changeShareRole(docId, share.user.id, e.target.value as ShareRole))}
              >
                <option value="viewer">Viewer</option>
                <option value="editor">Editor</option>
              </select>
              <button
                className="icon-btn"
                aria-label={`Remove ${share.user.name}`}
                title="Remove access"
                disabled={busy}
                onClick={() => void run(() => api.revokeShare(docId, share.user.id))}
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="share-footer">
        <button className="btn btn-primary" onClick={onClose}>
          Done
        </button>
      </div>
    </dialog>
  );
}

function Person({ name, email }: { name: string; email: string }) {
  return (
    <span className="person">
      <span className="avatar" aria-hidden="true">
        {name.charAt(0).toUpperCase()}
      </span>
      <span>
        <span className="person-name">{name}</span>
        <span className="muted small">{email}</span>
      </span>
    </span>
  );
}
