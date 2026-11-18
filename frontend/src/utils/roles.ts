import type { Role, ShareRole } from "../api/client";

export const ROLE_LABEL: Record<Role, string> = {
  owner: "Owner",
  editor: "Editor",
  commenter: "Commenter",
  viewer: "Viewer",
};

/** Roles that can be given when sharing, weakest first (matches the backend's ShareRole). */
export const SHARE_ROLES: ShareRole[] = ["viewer", "commenter", "editor"];

/** Everyone except viewers can add comments. */
export function canCommentRole(role: Role): boolean {
  return role !== "viewer";
}

/** Owners and editors can change content; commenters and viewers only read it. */
export function canEditRole(role: Role): boolean {
  return role === "owner" || role === "editor";
}
