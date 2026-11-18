import type { ActiveViewer } from "../api/client";

const COLORS = ["#1a73e8", "#d93025", "#188038", "#e37400", "#9334e6", "#007b83"];

/** Same user, same color, on every screen. */
function colorFor(id: string): string {
  let hash = 0;
  for (const char of id) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return COLORS[hash % COLORS.length];
}

function initials(name: string): string {
  const parts = name.split(/\s+/).filter(Boolean);
  return parts.slice(0, 2).map((part) => part[0].toUpperCase()).join("") || "?";
}

/** Small colored circles for the other people who have this document open. */
export function PresenceAvatars({ viewers }: { viewers: ActiveViewer[] }) {
  if (viewers.length === 0) return null;
  return (
    <ul className="presence" aria-label="Also in this document">
      {viewers.map((viewer) => {
        const label = `${viewer.name} (${viewer.is_editing ? "editing" : "viewing"})`;
        return (
          <li
            key={viewer.id}
            className={`presence-avatar${viewer.is_editing ? " presence-avatar-editing" : ""}`}
            style={{ background: colorFor(viewer.id) }}
            title={label}
            aria-label={label}
          >
            {initials(viewer.name)}
          </li>
        );
      })}
    </ul>
  );
}
