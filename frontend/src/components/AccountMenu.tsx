import { useCallback, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useDismiss } from "./useDismiss";

/** Round avatar with the signed-in user's initial; opens a card with their details and Sign out. */
export function AccountMenu() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const close = useCallback(() => setOpen(false), []);
  useDismiss(ref, open, close);

  if (!user) return null;

  async function signOut() {
    setOpen(false);
    await logout();
    navigate("/login");
  }

  return (
    <div className="menu" ref={ref}>
      <button
        className="account-avatar"
        aria-label={`Account: ${user.name}`}
        title={`${user.name}\n${user.email}`}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        {user.name.charAt(0).toUpperCase()}
      </button>
      {open && (
        <div className="menu-list account-card" role="menu">
          <div className="account-details">
            <span className="account-name">{user.name}</span>
            <span className="muted small">{user.email}</span>
          </div>
          <button role="menuitem" autoFocus onClick={() => void signOut()}>
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
