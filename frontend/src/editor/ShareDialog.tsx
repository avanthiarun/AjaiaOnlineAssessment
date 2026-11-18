import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError, type DemoUser, type Share, type ShareList, type ShareRole } from "../api/client";
import { useDismiss } from "../components/useDismiss";
import { ROLE_LABEL, SHARE_ROLES } from "../utils/roles";

interface Props {
  docId: string;
  open: boolean;
  onClose: () => void;
  /** Called after ownership moved to someone else (the caller is now an editor). */
  onTransferred: () => void;
}

function message(err: unknown): string {
  return err instanceof ApiError ? err.detail : "Something went wrong. Please try again.";
}

/** Owner-only modal: add people by email and manage their roles. */
export function ShareDialog({ docId, open, onClose, onTransferred }: Props) {
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

  async function makeOwner(share: Share) {
    const prompt = `Make ${share.user.name} the owner? You'll become an editor and can no longer share or delete this document.`;
    if (!window.confirm(prompt)) return;
    setBusy(true);
    setError("");
    try {
      await api.transferOwnership(docId, share.user.email);
      onTransferred();
    } catch (err) {
      setError(message(err));
    } finally {
      setBusy(false);
    }
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
        <RoleSelect label="Role" value={role} onChange={setRole} />
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
            <span className="muted">{ROLE_LABEL.owner}</span>
          </li>
          {access.shares.map((share) => (
            <li key={share.user.id}>
              <Person name={share.user.name} email={share.user.email} />
              <RoleSelect
                label={`Role for ${share.user.name}`}
                value={share.role}
                disabled={busy}
                onChange={(next) => void run(() => api.changeShareRole(docId, share.user.id, next))}
              />
              <PersonMenu
                name={share.user.name}
                disabled={busy}
                onMakeOwner={() => void makeOwner(share)}
                onRemove={() => void run(() => api.revokeShare(docId, share.user.id))}
              />
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

interface RoleSelectProps {
  label: string;
  value: ShareRole;
  disabled?: boolean;
  onChange: (role: ShareRole) => void;
}

function RoleSelect({ label, value, disabled, onChange }: RoleSelectProps) {
  return (
    <select aria-label={label} value={value} disabled={disabled} onChange={(e) => onChange(e.target.value as ShareRole)}>
      {SHARE_ROLES.map((option) => (
        <option key={option} value={option}>
          {ROLE_LABEL[option]}
        </option>
      ))}
    </select>
  );
}

interface PersonMenuProps {
  name: string;
  disabled: boolean;
  onMakeOwner: () => void;
  onRemove: () => void;
}

/** Per-person actions: transfer ownership or remove access. */
function PersonMenu({ name, disabled, onMakeOwner, onRemove }: PersonMenuProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const close = useCallback(() => setOpen(false), []);
  useDismiss(ref, open, close);

  function choose(action: () => void) {
    setOpen(false);
    action();
  }

  return (
    <div className="menu" ref={ref}>
      <button
        className="icon-btn"
        aria-label={`More actions for ${name}`}
        aria-haspopup="menu"
        aria-expanded={open}
        disabled={disabled}
        onClick={() => setOpen((value) => !value)}
      >
        ⋮
      </button>
      {open && (
        <div className="menu-list" role="menu">
          <button role="menuitem" autoFocus onClick={() => choose(onMakeOwner)}>
            Make owner
          </button>
          <button role="menuitem" className="danger" onClick={() => choose(onRemove)}>
            Remove access
          </button>
        </div>
      )}
    </div>
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
