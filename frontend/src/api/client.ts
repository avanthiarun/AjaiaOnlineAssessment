// Typed wrapper around the FastAPI backend. Every call sends the session cookie.

export type Role = "owner" | "editor" | "viewer";
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
  updateDocument: (id: string, changes: { title?: string; content_html?: string }) =>
    request<DocumentDetail>("PATCH", `/documents/${id}`, changes),
  deleteDocument: (id: string) => request<void>("DELETE", `/documents/${id}`),
  importDocument: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<DocumentDetail>("POST", "/documents/import", form);
  },
  exportUrl: (id: string, format: "md" | "html") => `/api/documents/${id}/export?format=${format}`,

  // Sharing
  listShares: (docId: string) => request<ShareList>("GET", `/documents/${docId}/shares`),
  addShare: (docId: string, email: string, role: ShareRole) =>
    request<Share>("POST", `/documents/${docId}/shares`, { email, role }),
  changeShareRole: (docId: string, userId: string, role: ShareRole) =>
    request<Share>("PATCH", `/documents/${docId}/shares/${userId}`, { role }),
  revokeShare: (docId: string, userId: string) => request<void>("DELETE", `/documents/${docId}/shares/${userId}`),
  leaveDocument: (docId: string) => request<void>("DELETE", `/documents/${docId}/shares/me`),
};
