import { describe, expect, it } from "vitest";
import type { Role } from "../api/client";
import { canCommentRole, canEditRole } from "./roles";

// Must match the backend's table in app/permissions.py (the server enforces it; this drives the UI).
const TABLE: [Role, boolean, boolean][] = [
  // role        can edit  can comment
  ["owner", true, true],
  ["editor", true, true],
  ["commenter", false, true],
  ["viewer", false, false],
];

describe("role helpers", () => {
  it.each(TABLE)("%s: edit=%s comment=%s", (role, edit, comment) => {
    expect(canEditRole(role)).toBe(edit);
    expect(canCommentRole(role)).toBe(comment);
  });
});
