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

export type ApiKeyItem = {
  id: string;
  name: string;
  key_prefix: string;
  created_at: string | null;
  revoked_at: string | null;
  active: boolean;
};

export type DataReadyStatus = {
  ready: boolean;
  products: number;
  orders: number;
  daily_metrics: number;
  csv_ready?: boolean;
  warehouse_ready?: boolean;
};

export type WarehouseConnection = {
  id: string;
  dialect: string;
  host: string;
  port: number;
  database: string;
  username: string;
  schema_name: string;
  status: string;
  last_verified_at: string | null;
  last_error: string | null;
  created_at: string | null;
  updated_at: string | null;
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

async function readErrorDetail(response: Response): Promise<string> {
  const raw = await response.text();
  if (!raw) {
    return `HTTP ${response.status} ${response.statusText}`;
  }
  try {
    const errorJson = JSON.parse(raw);
    if (typeof errorJson.detail === "string") return errorJson.detail;
    if (errorJson.detail?.reason) {
      return `${errorJson.detail.error}: ${errorJson.detail.reason}`;
    }
    if (errorJson.detail) return JSON.stringify(errorJson.detail);
    return raw;
  } catch {
    return raw;
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  opts: { auth?: boolean } = {}
): Promise<T> {
  const auth = opts.auth !== false;
  const base = getApiBaseUrl();
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const url = `${base}${normalizedPath}`;

  const headers = new Headers(options.headers || {});
  headers.set("Content-Type", "application/json");

  if (auth) {
    const token = getAccessToken();
    const apiKey = getApiKey();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    } else if (apiKey) {
      headers.set("X-API-Key", apiKey);
    }
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    throw new Error(
      "Unauthorized (401): Please log in or configure a valid API key."
    );
  }

  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }

  return response.json();
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
  }): Promise<AuthResponse> {
    const res = await request<AuthResponse>("/auth/join", {
      method: "POST",
      body: JSON.stringify(payload),
    }, { auth: false });
    return persistAuth(res);
  },

  async me(): Promise<{ user: AuthUser }> {
    return request<{ user: AuthUser }>("/auth/me");
  },

  async updateTenant(payload: { name: string }): Promise<{
    tenant: { id: string; name: string; slug: string };
  }> {
    return request("/auth/tenant", {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  async listApiKeys(): Promise<{ api_keys: ApiKeyItem[]; count: number }> {
    return request("/auth/api-keys");
  },

  async createApiKey(payload?: { name?: string }): Promise<{
    api_key: ApiKeyItem & { key: string };
    message: string;
  }> {
    return request("/auth/api-keys", {
      method: "POST",
      body: JSON.stringify(payload || { name: "default" }),
    });
  },

  async revokeApiKey(keyId: string): Promise<{ id: string; revoked: boolean }> {
    return request(`/auth/api-keys/${keyId}/revoke`, { method: "POST" });
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

  async uploadPlaybook(
    file: File,
    title?: string
  ): Promise<{ playbook: PlaybookItem; message: string }> {
    const base = getApiBaseUrl();
    const form = new FormData();
    form.append("file", file);
    if (title?.trim()) form.append("title", title.trim());

    const headers = new Headers();
    const token = getAccessToken();
    const apiKey = getApiKey();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    else if (apiKey) headers.set("X-API-Key", apiKey);

    const response = await fetch(`${base}/playbooks`, {
      method: "POST",
      headers,
      body: form,
    });

    if (response.status === 401) {
      throw new Error("Unauthorized (401): Please log in or configure a valid API key.");
    }
    if (!response.ok) {
      throw new Error(await readErrorDetail(response));
    }
    return response.json();
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

  async uploadCsv(
    file: File
  ): Promise<{ job: IngestJobItem; ready: DataReadyStatus; message: string }> {
    const base = getApiBaseUrl();
    const form = new FormData();
    form.append("file", file);

    const headers = new Headers();
    const token = getAccessToken();
    const apiKey = getApiKey();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    else if (apiKey) headers.set("X-API-Key", apiKey);

    const response = await fetch(`${base}/data/csv`, {
      method: "POST",
      headers,
      body: form,
    });

    if (response.status === 401) {
      throw new Error("Unauthorized (401): Please log in or configure a valid API key.");
    }
    if (!response.ok) {
      throw new Error(await readErrorDetail(response));
    }
    return response.json();
  },

  async getWarehouse(): Promise<{ connection: WarehouseConnection | null }> {
    return request("/warehouse");
  },

  async testWarehouse(payload: {
    host: string;
    port: number;
    database: string;
    username: string;
    password: string;
    schema_name?: string;
  }): Promise<{ ok: boolean; missing_tables: string[]; error: string | null }> {
    return request("/warehouse/test", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async saveWarehouse(payload: {
    host: string;
    port: number;
    database: string;
    username: string;
    password: string;
    schema_name?: string;
  }): Promise<{ connection: WarehouseConnection; message: string }> {
    return request("/warehouse", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },

  async deleteWarehouse(): Promise<{ deleted: boolean }> {
    return request("/warehouse", { method: "DELETE" });
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

  async runInvestigation(payload: {
    question: string;
    wait?: boolean;
  }): Promise<InvestigationDetail> {
    return request<InvestigationDetail>("/investigations", {
      method: "POST",
      body: JSON.stringify({
        question: payload.question,
        wait: payload.wait ?? true,
      }),
    });
  },

  async submitReview(
    investigationId: string,
    payload: {
      decision: ReviewDecision;
      reviewer: string;
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
};
