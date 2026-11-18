import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { AccountMenu } from "./AccountMenu";

interface Props {
  /** Page-specific header content (the editor puts the title, menus and actions here). */
  children?: ReactNode;
  /** Replaces the logo link's plain navigation, e.g. so the editor can save before leaving. */
  onHome?: () => void;
}

/** App header like Google Docs: logo (home), page content, account avatar. */
export function TopBar({ children, onHome }: Props) {
  const logo = <img src="/favicon.svg" alt="" width={children ? 30 : 24} height={children ? 40 : 32} />;
  return (
    <header className={`topbar${children ? " topbar-editor" : ""}`}>
      {onHome ? (
        <button className="topbar-brand" aria-label="Back to documents" title="Back to documents" onClick={onHome}>
          {logo}
        </button>
      ) : (
        <Link to="/" className="topbar-brand" aria-label="Ajaia Docs home">
          {logo}
          {!children && <span>Ajaia Docs</span>}
        </Link>
      )}
      <div className="topbar-middle">{children}</div>
      <AccountMenu />
    </header>
  );
}
