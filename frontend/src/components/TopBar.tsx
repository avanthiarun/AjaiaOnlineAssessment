import type { ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

/** App header: logo on the left, optional page content in the middle, user + sign out on the right. */
export function TopBar({ children }: { children?: ReactNode }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function handleSignOut() {
    await logout();
    navigate("/login");
  }

  return (
    <header className="topbar">
      <Link to="/" className="topbar-brand">
        <img src="/favicon.svg" alt="" width={24} height={32} />
        <span>Ajaia Docs</span>
      </Link>
      <div className="topbar-middle">{children}</div>
      {user && (
        <div className="topbar-user">
          <span className="topbar-name" title={user.email}>
            {user.name}
          </span>
          <button className="btn" onClick={handleSignOut}>
            Sign out
          </button>
        </div>
      )}
    </header>
  );
}
