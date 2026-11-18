// Typed wrapper around the FastAPI backend. Every call sends the session cookie.

export type Role = "owner" | "editor" | "commenter" | "viewer";
export type ShareRole = Exclude<Role, "owner">;

export interface User {
  id: string;
  email: string;
  name: string;
}

export interface DemoUser {
  email: string;
  name: string;
}

export interface DocumentSummary {
  id: string;
  title: string;
  owner: User;
  role: Role;
  updated_at: string;
  version: number;
}

export interface DocumentDetail extends DocumentSummary {
  content_html: string;
}

export interface DocumentList {
  owned: DocumentSummary[];
  shared: DocumentSummary[];
}

export interface Share {
  user: User;
  role: ShareRole;
}

export interface ImportInfo {
  extensions: string[];
  max_mb: number;
}

export interface ActiveViewer {
  id: string;
  name: string;
  role: Role;
  is_editing: boolean;
}

export interface Presence {
  viewers: ActiveViewer[];
  version: number;
  updated_at: string;
}

export interface VersionSummary {
  id: string;
  created_at: string;
  created_by: string;
}

export interface VersionDetail extends VersionSummary {
  title: string;
  content_html: string;
}

/** quote and body are plain text: always render them as text, never as HTML. */
export interface Comment {
  id: string;
  author: User;
  quote: string;
  body: string;
  resolved: boolean;
  created_at: string;
  can_resolve: boolean;
  can_delete: boolean;
}

export interface ShareList {
  owner: User;
  shares: Share[];
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

type Method = "GET" | "POST" | "PATCH" | "DELETE";

/** FastAPI returns a string detail, or a list of validation errors for 422. */
function readDetail(body: unknown, fallback: string): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d: { msg?: string }) => d.msg?.replace(/^Value error, /, "") ?? "").join("; ");
  }
  return fallback;
}

async function request<T>(method: Method, path: string, body?: unknown): Promise<T> {
  const isForm = body instanceof FormData;
  const response = await fetch(`/api${path}`, {
    method,
    credentials: "include",
    headers: body === undefined || isForm ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
  });
  if (response.status === 204) return undefined as T;
  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, readDetail(data, response.statusText));
  return data as T;
}

export const api = {
  // Auth
  me: () => request<User>("GET", "/auth/me"),
  login: (email: string, password: string) => request<User>("POST", "/auth/login", { email, password }),
  logout: () => request<void>("POST", "/auth/logout"),
  demoUsers: () => request<DemoUser[]>("GET", "/auth/demo-users"),

  // Documents
  listDocuments: () => request<DocumentList>("GET", "/documents"),
  createDocument: (title?: string) => request<DocumentDetail>("POST", "/documents", { title }),
  getDocument: (id: string) => request<DocumentDetail>("GET", `/documents/${id}`),
  updateDocument: (id: string, changes: { title?: string; content_html?: string; base_version?: number }) =>
    request<DocumentDetail>("PATCH", `/documents/${id}`, changes),
  deleteDocument: (id: string) => request<void>("DELETE", `/documents/${id}`),
  importDocument: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<DocumentDetail>("POST", "/documents/import", form);
  },
  importInfo: () => request<ImportInfo>("GET", "/documents/import/info"),
  presence: (id: string, editing: boolean) => request<Presence>("POST", `/documents/${id}/presence`, { editing }),
  exportUrl: (id: string, format: "md" | "html") => `/api/documents/${id}/export?format=${format}`,
  listComments: (id: string) => request<Comment[]>("GET", `/documents/${id}/comments`),
  createComment: (id: string, comment: { quote: string; body: string }) =>
    request<Comment>("POST", `/documents/${id}/comments`, comment),
  setCommentResolved: (id: string, commentId: string, resolved: boolean) =>
    request<Comment>("PATCH", `/documents/${id}/comments/${commentId}`, { resolved }),
  deleteComment: (id: string, commentId: string) => request<void>("DELETE", `/documents/${id}/comments/${commentId}`),
  listVersions: (id: string) => request<VersionSummary[]>("GET", `/documents/${id}/versions`),
  getVersion: (id: string, versionId: string) => request<VersionDetail>("GET", `/documents/${id}/versions/${versionId}`),
  restoreVersion: (id: string, versionId: string) =>
    request<DocumentDetail>("POST", `/documents/${id}/versions/${versionId}/restore`),

  // Sharing
  listShares: (docId: string) => request<ShareList>("GET", `/documents/${docId}/shares`),
  addShare: (docId: string, email: string, role: ShareRole) =>
    request<Share>("POST", `/documents/${docId}/shares`, { email, role }),
  changeShareRole: (docId: string, userId: string, role: ShareRole) =>
    request<Share>("PATCH", `/documents/${docId}/shares/${userId}`, { role }),
  revokeShare: (docId: string, userId: string) => request<void>("DELETE", `/documents/${docId}/shares/${userId}`),
  transferOwnership: (docId: string, email: string) =>
    request<DocumentDetail>("POST", `/documents/${docId}/transfer`, { email }),
  leaveDocument: (docId: string) => request<void>("DELETE", `/documents/${docId}/shares/me`),
};
