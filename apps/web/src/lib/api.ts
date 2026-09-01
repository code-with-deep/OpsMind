import {
  CaseSummaryItem,
  InvestigationDetail,
  InvestigationSummaryItem,
  ReviewDecision,
  SqlTemplate,
} from "../types";

const STORAGE_KEY = "opsmind_api_key";
const DEFAULT_DEV_KEY = "change-me-opsmind-dev-key";

export function getApiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL;
  if (typeof configured === "string" && configured.trim().length > 0) {
    return configured.trim().replace(/\/$/, "");
  }

  // Vite dev server proxies API routes to the backend container.
  if (import.meta.env.DEV) {
    return "";
  }

  // Docker / local production build: web on :3000, API on :8000.
  if (typeof window !== "undefined") {
    const { protocol, hostname } = window.location;
    if (hostname === "localhost" || hostname === "127.0.0.1") {
      return `${protocol}//${hostname}:8000`;
    }
  }

  // Deployed behind a single gateway — use same origin.
  return "";
}

export function getApiKey(): string {
  const stored = localStorage.getItem(STORAGE_KEY);
  return stored ? stored.trim() : DEFAULT_DEV_KEY;
}

export function setApiKey(key: string): void {
  localStorage.setItem(STORAGE_KEY, key.trim());
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const apiKey = getApiKey();
  const base = getApiBaseUrl();
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const url = `${base}${normalizedPath}`;

  const headers = new Headers(options.headers || {});
  headers.set("Content-Type", "application/json");
  if (apiKey) {
    headers.set("X-API-Key", apiKey);
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    throw new Error(
      "Unauthorized (401): Invalid or missing OpsMind API Key. Please configure your API key."
    );
  }

  if (!response.ok) {
    let errorDetail = "";
    try {
      const errorJson = await response.json();
      if (typeof errorJson.detail === "string") {
        errorDetail = errorJson.detail;
      } else if (errorJson.detail?.reason) {
        errorDetail = `${errorJson.detail.error}: ${errorJson.detail.reason}`;
      } else if (errorJson.detail) {
        errorDetail = JSON.stringify(errorJson.detail);
      }
    } catch {
      errorDetail = await response.text();
    }
    throw new Error(errorDetail || `HTTP ${response.status} ${response.statusText}`);
  }

  return response.json();
}

export const api = {
  // System Health
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

  // Investigations
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

  // Case Memory
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

  // Tools demo
  async getSqlTemplates(): Promise<{ templates: SqlTemplate[] }> {
    return request<{ templates: SqlTemplate[] }>("/tools/sql/templates");
  },
};
