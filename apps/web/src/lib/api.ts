import {
  CaseSummaryItem,
  InvestigationDetail,
  InvestigationSummaryItem,
  ReviewDecision,
  SqlTemplate,
} from "../types";

const API_KEY_STORAGE = "opsmind_api_key";
const JWT_STORAGE = "opsmind_access_token";
const USER_STORAGE = "opsmind_user";

/** Demo-tenant bootstrap key (must be pasted explicitly — never auto-injected). */
export const DEMO_BOOTSTRAP_API_KEY = "change-me-opsmind-dev-key";

export type AuthUser = {
  id: string;
  email: string;
  role: string;
  tenant: { id: string; name: string; slug: string };
};

export type InviteItem = {
  id: string;
  code_prefix: string;
  max_uses: number;
  use_count: number;
  expires_at: string | null;
  created_at: string | null;
  revoked_at: string | null;
  active: boolean;
};

export type PlaybookItem = {
  id: string;
  doc_key: string;
  title: string;
  chunk_count: number;
  content_hash: string;
  created_at: string | null;
  updated_at: string | null;
};

export type IngestJobItem = {
  id: string;
  kind: string;
  filename: string;
  status: string;
  row_counts: Record<string, number>;
  error: string | null;
  created_at: string | null;
  completed_at: string | null;
};


export type DataReadyStatus = {
  ready: boolean;
  products: number;
  orders: number;
  daily_metrics: number;
};

export type AccessRequest = {
  id: string;
  requester_email: string;
  status: 'pending' | 'approved' | 'rejected';
  created_at: string;
  reviewed_at: string | null;
  reviewed_by_email: string | null;
  rejection_reason: string | null;
  invite_code_prefix: string | null;
};

export type AccessUser = {
  id: string;
  email: string;
  role: string;
  status: 'active' | 'revoked';
  created_at: string;
  revoked_at: string | null;
  invite_date: string | null;
  approved_at: string | null;
  approved_by_email: string | null;
};

export type NotificationItem = {
  id: string;
  type: string;
  title: string;
  body: string;
  is_read: boolean;
  created_at: string;
  related_entity_id: string | null;
  related_entity_type: string | null;
};

export type AccessRequestStatus = {
  status: 'pending' | 'approved' | 'rejected';
  message: string;
  rejection_reason?: string | null;
};

export type OnboardingSuggestion = {
  kind: "revenue" | "stockout" | "carrier" | "returns";
  title: string;
  question: string;
};

/** Setup progress for the get-started checklist (GET /onboarding/status). */
export type OnboardingStatus = {
  is_admin: boolean;
  ready_to_investigate: boolean;
  missing: Array<"business_data" | "playbooks">;
  steps: {
    business_data: { done: boolean; products: number; orders: number };
    playbooks: { done: boolean; count: number };
    first_investigation: { done: boolean; count: number; latest_id: string | null };
    first_review: { done: boolean };
    team: { done: boolean; invites: number; members: number };
  };
  data_coverage: { start: string; end: string } | null;
  suggested_questions: OnboardingSuggestion[];
  sample_data_available: boolean;
};

export type JoinPendingResponse = {
  status: 'pending';
  message: string;
  request_id: string;
};

export function getApiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL;
  if (typeof configured === "string" && configured.trim().length > 0) {
    return configured.trim().replace(/\/$/, "");
  }

  if (import.meta.env.DEV) {
    return "";
  }

  if (typeof window !== "undefined") {
    const { protocol, hostname } = window.location;
    if (hostname === "localhost" || hostname === "127.0.0.1") {
      return `${protocol}//${hostname}:8000`;
    }
  }

  return "";
}

export function getAccessToken(): string | null {
  const token = localStorage.getItem(JWT_STORAGE);
  return token ? token.trim() : null;
}

export function setAccessToken(token: string | null): void {
  if (!token) {
    localStorage.removeItem(JWT_STORAGE);
    return;
  }
  localStorage.setItem(JWT_STORAGE, token.trim());
}

export function getStoredUser(): AuthUser | null {
  try {
    const raw = localStorage.getItem(USER_STORAGE);
    if (!raw) return null;
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

export function setStoredUser(user: AuthUser | null): void {
  if (!user) {
    localStorage.removeItem(USER_STORAGE);
    return;
  }
  localStorage.setItem(USER_STORAGE, JSON.stringify(user));
}

export function clearSession(): void {
  setAccessToken(null);
  setStoredUser(null);
  clearApiKey();
}

export function getApiKey(): string {
  const stored = localStorage.getItem(API_KEY_STORAGE);
  return stored ? stored.trim() : "";
}

export function setApiKey(key: string): void {
  const trimmed = key.trim();
  if (!trimmed) {
    localStorage.removeItem(API_KEY_STORAGE);
    return;
  }
  localStorage.setItem(API_KEY_STORAGE, trimmed);
}

export function clearApiKey(): void {
  localStorage.removeItem(API_KEY_STORAGE);
}

export function hasAuthCredentials(): boolean {
  return Boolean(getAccessToken() || getApiKey());
}

/**
 * App shell (Console / History / Settings) requires a real company session (JWT).
 * A pasted API key alone must NOT unlock the UI — that caused "Sign in" + History
 * while talking to the empty demo tenant.
 *
 * API keys remain available after login (Tools / programmatic) via the header modal.
 */
export function canAccessApp(): boolean {
  return Boolean(getAccessToken());
}

/** Error thrown by every API call. `message` is always safe to show to users. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string | null;
  /** Server-side validation messages keyed by request field name. */
  readonly fieldErrors: Record<string, string>;

  constructor(
    message: string,
    status: number,
    code: string | null = null,
    fieldErrors: Record<string, string> = {}
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.fieldErrors = fieldErrors;
  }
}

const NETWORK_ERROR_MESSAGE =
  "Can't reach the OpsMind server. Check your internet connection and try again.";

function messageForStatus(status: number): string {
  if (status === 400) return "That request couldn't be processed. Please check your input and try again.";
  if (status === 401) return "Your session has expired. Please sign in again.";
  if (status === 403) return "You don't have permission to do that. Contact your workspace admin.";
  if (status === 404) return "We couldn't find that. It may have been deleted.";
  if (status === 409) return "This conflicts with existing data. Refresh and try again.";
  if (status === 413) return "The file is too large. Please upload a smaller file.";
  if (status === 422) return "Some fields need attention. Please check the form and try again.";
  if (status === 429) return "Too many attempts. Please wait a moment and try again.";
  if (status >= 500) return "Something went wrong on our side. Please try again in a moment.";
  return "Something went wrong. Please try again.";
}

/** Developer-facing server messages mapped to something a user can act on. */
const SERVER_MESSAGE_REWRITES: Array<[RegExp, string]> = [
  [/admin role required/i, "Only workspace admins can do this."],
  [/user session required/i, "Please sign in with your email and password to do this."],
  [/missing or invalid (api key|credentials)/i, "Your session has expired. Please sign in again."],
];

async function toApiError(response: Response): Promise<ApiError> {
  let body: { detail?: unknown; errors?: Array<{ field?: string; message?: string }> } | null = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }

  const fieldErrors: Record<string, string> = {};
  for (const e of Array.isArray(body?.errors) ? body.errors : []) {
    if (e.field && e.message && !fieldErrors[e.field]) fieldErrors[e.field] = e.message;
  }

  const detail = body?.detail;
  let message = "";
  let code: string | null = null;
  if (typeof detail === "string") {
    message = detail;
  } else if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const d = detail as { error?: string; reason?: string; request_id?: string };
    code = d.error ?? null;
    if (d.reason) message = d.reason;
    else if (code === "internal_error")
      message = `${messageForStatus(500)}${d.request_id ? ` (Reference: ${d.request_id})` : ""}`;
  }
  for (const [pattern, friendly] of SERVER_MESSAGE_REWRITES) {
    if (pattern.test(message)) message = friendly;
  }
  return new ApiError(message || messageForStatus(response.status), response.status, code, fieldErrors);
}

export function authHeaders(): Headers {
  const headers = new Headers();
  const token = getAccessToken();
  const apiKey = getApiKey();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  else if (apiKey) headers.set("X-API-Key", apiKey);
  return headers;
}

/** Endpoints where a 401 means "wrong password" rather than "session expired". */
const CREDENTIAL_CHECK_PATHS = new Set(["/auth/login", "/auth/change-password"]);

async function send(
  path: string,
  init: RequestInit = {},
  opts: { auth?: boolean } = {}
): Promise<Response> {
  const auth = opts.auth !== false;
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const headers = auth ? authHeaders() : new Headers();
  new Headers(init.headers || {}).forEach((value, key) => headers.set(key, value));
  if (typeof init.body === "string" && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}${normalizedPath}`, { ...init, headers });
  } catch {
    throw new ApiError(NETWORK_ERROR_MESSAGE, 0, "network_error");
  }

  const pathOnly = normalizedPath.split("?")[0];
  if (response.status === 401 && auth && !CREDENTIAL_CHECK_PATHS.has(pathOnly)) {
    // P1-9: outside credential checks a 401 means the session expired — clear
    // it and send the user to /login instead of a confusing inline error.
    clearSession();
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      window.location.href = "/login?notice=session_expired";
    }
    throw new ApiError("Your session has expired. Please sign in again.", 401, "session_expired");
  }
  if (!response.ok) throw await toApiError(response);
  return response;
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  opts: { auth?: boolean } = {}
): Promise<T> {
  const response = await send(path, options, opts);
  return response.json() as Promise<T>;
}

/** Fetch an authenticated binary file and save it via the browser's normal
 * download flow (auth needs a header, so a plain `<a href>` won't carry it). */
async function downloadAuthedFile(path: string, filename: string): Promise<void> {
  const response = await send(path);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  try {
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
  } finally {
    URL.revokeObjectURL(url);
  }
}

/** A user-facing message for any thrown value. */
export function errorMessage(err: unknown, fallback: string): string {
  return err instanceof Error && err.message ? err.message : fallback;
}

type AuthResponse = {
  access_token: string;
  token_type: string;
  expires_in_hours: number;
  user: AuthUser;
};

function persistAuth(res: AuthResponse): AuthResponse {
  setAccessToken(res.access_token);
  setStoredUser(res.user);
  return res;
}

export const api = {
  async checkHealth(): Promise<{ status: string; service: string; env?: string }> {
    const base = getApiBaseUrl();
    const res = await fetch(`${base}/health`);
    if (!res.ok) throw new Error("Health check failed");
    return res.json();
  },

  async checkReady(): Promise<{ status: string; checks: Record<string, string> }> {
    const base = getApiBaseUrl();
    const res = await fetch(`${base}/ready`);
    if (!res.ok) throw new Error("Readiness check failed");
    return res.json();
  },

  async signup(payload: {
    company_name: string;
    email: string;
    password: string;
  }): Promise<AuthResponse> {
    const res = await request<AuthResponse>("/auth/signup", {
      method: "POST",
      body: JSON.stringify(payload),
    }, { auth: false });
    return persistAuth(res);
  },

  async login(payload: { email: string; password: string }): Promise<AuthResponse> {
    const res = await request<AuthResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    }, { auth: false });
    return persistAuth(res);
  },

  async joinInvite(payload: {
    invite_code: string;
    email: string;
    password: string;
  }): Promise<JoinPendingResponse> {
    return request<JoinPendingResponse>("/auth/join", {
      method: "POST",
      body: JSON.stringify(payload),
    }, { auth: false });
  },

  async checkRequestStatus(email: string, invite_code: string): Promise<AccessRequestStatus> {
    const params = new URLSearchParams({ email, invite_code });
    return request<AccessRequestStatus>(`/auth/request-status?${params.toString()}`, {}, { auth: false });
  },

  async me(): Promise<{ user: AuthUser }> {
    return request<{ user: AuthUser }>("/auth/me");
  },

  async changePassword(payload: {
    current_password: string;
    new_password: string;
  }): Promise<AuthResponse> {
    const res = await request<AuthResponse>("/auth/change-password", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    return persistAuth(res);
  },

  async forgotPassword(payload: { email: string }): Promise<{ message: string }> {
    return request<{ message: string }>(
      "/auth/forgot-password",
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
      { auth: false },
    );
  },

  async resetPassword(payload: {
    token: string;
    new_password: string;
  }): Promise<{ message: string }> {
    return request<{ message: string }>(
      "/auth/reset-password",
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
      { auth: false },
    );
  },

  async updateTenant(payload: { name: string }): Promise<{
    tenant: { id: string; name: string; slug: string };
  }> {
    return request("/auth/tenant", {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  async listInvites(): Promise<{ invites: InviteItem[]; count: number }> {
    return request("/auth/invites");
  },

  async createInvite(payload?: {
    max_uses?: number;
    ttl_days?: number;
  }): Promise<{
    invite: InviteItem & { code: string };
    message: string;
  }> {
    return request("/auth/invites", {
      method: "POST",
      body: JSON.stringify(payload || {}),
    });
  },

  async revokeInvite(inviteId: string): Promise<{ id: string; revoked: boolean }> {
    return request(`/auth/invites/${inviteId}/revoke`, { method: "POST" });
  },

  async listPlaybooks(): Promise<{ playbooks: PlaybookItem[]; count: number }> {
    return request("/playbooks");
  },

  /** Upload one .md/.markdown/.txt playbook, or a .zip of several — the ZIP
   * is extracted server-side and every playbook inside is ingested. */
  async uploadPlaybook(
    file: File,
    title?: string
  ): Promise<{
    playbook?: PlaybookItem;
    playbooks: PlaybookItem[];
    errors?: { filename: string; error: string }[];
    count: number;
    message: string;
  }> {
    const form = new FormData();
    form.append("file", file);
    if (title?.trim()) form.append("title", title.trim());
    return (await send("/playbooks", { method: "POST", body: form })).json();
  },

  async deletePlaybook(documentId: string): Promise<{ id: string; deleted: boolean }> {
    return request(`/playbooks/${documentId}`, { method: "DELETE" });
  },

  async dataReady(): Promise<DataReadyStatus> {
    return request("/data/ready");
  },

  async listIngestJobs(): Promise<{ jobs: IngestJobItem[]; count: number }> {
    return request("/data/ingest-jobs");
  },

  async deleteIngestJob(jobId: string): Promise<{ deleted: boolean; wiped_business_data: boolean; ready: boolean; message: string }> {
    return request(`/data/ingest-jobs/${jobId}`, { method: "DELETE" });
  },

  async deleteBusinessData(): Promise<{ deleted: Record<string, number>; ready: boolean; message: string }> {
    return request("/data/csv", { method: "DELETE" });
  },

  async uploadCsv(
    file: File
  ): Promise<{ job: IngestJobItem; ready: DataReadyStatus; message: string }> {
    const form = new FormData();
    form.append("file", file);
    return (await send("/data/csv", { method: "POST", body: form })).json();
  },

  /** Download the sample CSV ZIP (own standalone dataset — not the shared demo
   * tenant's data) and save it via the browser's normal download flow. */
  async downloadSampleTemplate(): Promise<void> {
    return downloadAuthedFile("/data/sample-template", "opsmind_sample_data.zip");
  },

  /** Download the sample SOP playbooks (5 .md files, zipped) tuned to the
   * sample CSV bundle's planted scenario. Extract and upload each .md
   * individually via "Upload SOP" — playbook uploads are one file at a time. */
  async downloadSamplePlaybooks(): Promise<void> {
    return downloadAuthedFile("/playbooks/sample-template", "opsmind_sample_playbooks.zip");
  },

  async getOnboardingStatus(): Promise<OnboardingStatus> {
    return request<OnboardingStatus>("/onboarding/status");
  },

  /** Loads the sample store (CSV bundle + playbooks) into this workspace;
   * never replaces business data or playbooks the workspace already has. */
  async loadSampleData(): Promise<{
    loaded: { business_data: boolean; playbooks: number };
    message: string;
  }> {
    return request("/onboarding/sample-data", { method: "POST" });
  },

  async listInvestigations(params?: {
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<{
    investigations: InvestigationSummaryItem[];
    count: number;
  }> {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.set("status", params.status);
    if (params?.limit) searchParams.set("limit", params.limit.toString());
    if (params?.offset) searchParams.set("offset", params.offset.toString());

    const qs = searchParams.toString();
    return request<{ investigations: InvestigationSummaryItem[]; count: number }>(
      `/investigations${qs ? `?${qs}` : ""}`
    );
  },

  async getInvestigation(id: string): Promise<InvestigationDetail> {
    return request<InvestigationDetail>(`/investigations/${id}`);
  },

  /** Starts an investigation. By default it runs in the background and this
   * resolves immediately with the `running` investigation; progress then
   * arrives through the live event stream. */
  async runInvestigation(payload: {
    question: string;
    wait?: boolean;
  }): Promise<InvestigationDetail> {
    return request<InvestigationDetail>("/investigations", {
      method: "POST",
      body: JSON.stringify({
        question: payload.question,
        wait: payload.wait ?? false,
      }),
    });
  },

  async submitReview(
    investigationId: string,
    payload: {
      decision: ReviewDecision;
      notes?: string;
    }
  ): Promise<{
    review: {
      id: string;
      decision: ReviewDecision;
      reviewer: string;
      notes: string | null;
      created_at: string;
    };
    case_promoted: boolean;
    case_summary?: {
      id: string;
      title: string;
      confidence: number;
    } | null;
  }> {
    return request(`/investigations/${investigationId}/reviews`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async getCaseMemory(params?: { limit?: number; offset?: number }): Promise<{
    cases: CaseSummaryItem[];
    count: number;
  }> {
    const searchParams = new URLSearchParams();
    if (params?.limit) searchParams.set("limit", params.limit.toString());
    if (params?.offset) searchParams.set("offset", params.offset.toString());
    const qs = searchParams.toString();

    return request<{ cases: CaseSummaryItem[]; count: number }>(
      `/investigations/cases/memory${qs ? `?${qs}` : ""}`
    );
  },

  async getSqlTemplates(): Promise<{ templates: SqlTemplate[] }> {
    return request<{ templates: SqlTemplate[] }>("/tools/sql/templates");
  },

  // ── Access Management ────────────────────────────────────────────────────

  async listAccessRequests(status?: string): Promise<{ requests: AccessRequest[]; count: number }> {
    const params = status && status !== "all" ? `?status=${encodeURIComponent(status)}` : "?status=all";
    return request(`/access/requests${params}`);
  },

  async approveAccessRequest(id: string): Promise<{ status: string }> {
    return request(`/access/requests/${id}/approve`, { method: "POST" });
  },

  async rejectAccessRequest(id: string, reason?: string): Promise<{ status: string }> {
    return request(`/access/requests/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason: reason ?? null }),
    });
  },

  async listAccessUsers(status?: string): Promise<{ users: AccessUser[]; count: number }> {
    const params = status && status !== "all" ? `?status=${encodeURIComponent(status)}` : "";
    return request(`/access/users${params}`);
  },

  async revokeUserAccess(userId: string, reason?: string): Promise<{ revoked: boolean }> {
    return request(`/access/users/${userId}/revoke`, {
      method: "POST",
      body: JSON.stringify({ reason: reason ?? null }),
    });
  },

  // ── Notifications ────────────────────────────────────────────────────────

  async listNotifications(limit = 20): Promise<{ notifications: NotificationItem[]; count: number }> {
    return request(`/notifications?limit=${limit}`);
  },

  async getUnreadCount(): Promise<{ count: number }> {
    return request("/notifications/unread-count");
  },

  async markNotificationRead(id: string): Promise<{ read: boolean }> {
    return request(`/notifications/${id}/read`, { method: "POST" });
  },

  async markAllNotificationsRead(): Promise<{ marked_read: number }> {
    return request("/notifications/read-all", { method: "POST" });
  },
};
