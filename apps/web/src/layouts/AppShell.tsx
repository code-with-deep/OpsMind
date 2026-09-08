import { useEffect, useState } from "react";
import { Link, Outlet, useLocation, useNavigate, useParams } from "react-router-dom";
import {
  InvestigationDetail,
  InvestigationSummaryItem,
  ReviewDecision,
} from "../types";
import { api } from "../lib/api";
import { Header } from "../components/layout/Header";
import { AuditDrawer } from "../components/investigation/AuditDrawer";
import { NewInvestigationModal } from "../components/investigation/NewInvestigationModal";
import { parseConsoleSubView, routes } from "../lib/routes";
import { AlertTriangle, ArrowRight } from "lucide-react";

export interface AppShellOutletContext {
  investigations: InvestigationSummaryItem[];
  currentInvestigation: InvestigationDetail | null;
  loading: boolean;
  submittingReview: boolean;
  activeSubView: ReturnType<typeof parseConsoleSubView>;
  selectedSourceId: string | null;
  approvedCount: number;
  loadDetail: (id: string) => Promise<void>;
  handleLaunchInvestigation: (question: string) => Promise<void>;
  handleSubmitReview: (payload: {
    decision: ReviewDecision;
    reviewer: string;
    notes?: string;
  }) => Promise<void>;
  handleSelectSource: (sourceId: string) => void;
  setActiveSubView: (view: ReturnType<typeof parseConsoleSubView>) => void;
  setSelectedSourceId: (id: string | null) => void;
  openNewInvestigationModal: () => void;
  openAuditDrawer: () => void;
}

type LaunchLocationState = {
  launchQuestion?: string;
};

type AppNotice = {
  title: string;
  body: string;
  actionTo?: string;
  actionLabel?: string;
};

function toAppNotice(raw: string): AppNotice {
  const text = (raw || "").trim();
  const lower = text.toLowerCase();

  // ── Data readiness ────────────────────────────────────────────────────────
  if (
    lower.includes("tenant_data_not_ready") ||
    lower.includes("upload company csv") ||
    lower.includes("no business data") ||
    (lower.includes("products.csv") && lower.includes("orders.csv"))
  ) {
    return {
      title: "Business data required",
      body: "Upload a company data ZIP in Settings before running investigations. Include products.csv, orders.csv, and order_items.csv.",
      actionTo: routes.settings,
      actionLabel: "Go to Settings",
    };
  }

  // ── Guardrails ────────────────────────────────────────────────────────────
  if (
    lower.includes("guardrail") ||
    lower.includes("jailbreak") ||
    lower.includes("injection") ||
    lower.includes("flagged as potentially")
  ) {
    return {
      title: "Question flagged",
      body: "Your question was flagged as potentially unsafe. Please rephrase it — avoid instructions, code, or requests that aren't operations questions.",
    };
  }

  // ── Investigation pipeline failures ───────────────────────────────────────
  if (lower.includes("investigation_in_progress") || lower.includes("already in progress")) {
    return {
      title: "Investigation already running",
      body: "An investigation is already in progress for your workspace. Wait for it to finish before starting another.",
    };
  }

  if (lower.includes("fail_soft") || lower.includes("could not reach a confident") || lower.includes("ran out of retries")) {
    return {
      title: "Investigation incomplete",
      body: "The agents couldn't reach a confident answer. Try rephrasing your question or uploading more business data and playbooks.",
    };
  }

  if (lower.includes("needs_clarification") || lower.includes("more context")) {
    return {
      title: "Question needs more detail",
      body: "The question was too broad or ambiguous. Add specifics like a date range, product category, or region.",
    };
  }

  // ── Auth ──────────────────────────────────────────────────────────────────
  if (lower.includes("session has expired") || lower.includes("unauthorized") || lower.includes("sign in again")) {
    return {
      title: "Session expired",
      body: "Your session has expired. Please sign in again to continue.",
      actionTo: routes.login,
      actionLabel: "Sign in",
    };
  }

  if (lower.includes("don't have permission") || lower.includes("forbidden")) {
    return {
      title: "Access denied",
      body: "You don't have permission to perform this action. Contact your workspace admin.",
      actionTo: routes.settings,
      actionLabel: "Go to Settings",
    };
  }

  // ── Network / server ──────────────────────────────────────────────────────
  if (lower.includes("could not reach the server") || lower.includes("network") || lower.includes("econnrefused")) {
    return {
      title: "Connection problem",
      body: "Could not reach the server. Check your network connection and try again.",
    };
  }

  if (lower.includes("timed out") || lower.includes("timeout")) {
    return {
      title: "Request timed out",
      body: "The investigation took too long to respond. Please try again.",
    };
  }

  if (lower.includes("server encountered an unexpected") || lower.includes("500")) {
    return {
      title: "Server error",
      body: "The server encountered an unexpected error. Please try again in a moment.",
    };
  }

  // ── Generic fallback ──────────────────────────────────────────────────────
  return {
    title: "Something went wrong",
    body: text || "An unexpected error occurred. Try again or contact support.",
  };
}

export function AppShell() {
  const navigate = useNavigate();
  const location = useLocation();
  const { investigationId, subView } = useParams<{
    investigationId?: string;
    subView?: string;
  }>();

  const [investigations, setInvestigations] = useState<InvestigationSummaryItem[]>([]);
  const [currentInvestigation, setCurrentInvestigation] =
    useState<InvestigationDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [isNewModalOpen, setIsNewModalOpen] = useState(false);
  const [isAuditDrawerOpen, setIsAuditDrawerOpen] = useState(false);
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);
  const [submittingReview, setSubmittingReview] = useState(false);
  const [globalError, setGlobalError] = useState<string | null>(null);
  const notice = globalError ? toAppNotice(globalError) : null;

  const activeSubView = parseConsoleSubView(subView);
  const approvedCount = investigations.filter((i) => i.is_approved).length;

  const loadHistory = async () => {
    try {
      const res = await api.listInvestigations();
      setInvestigations(res.investigations || []);
      return res.investigations || [];
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "History load failed";
      console.warn("History load error:", message);
      return [];
    }
  };

  const loadDetail = async (id: string) => {
    setLoading(true);
    setGlobalError(null);
    try {
      const detail = await api.getInvestigation(id);
      setCurrentInvestigation(detail);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to load investigation details.";
      setGlobalError(message);
    } finally {
      setLoading(false);
    }
  };

  /** Silently refresh investigation data without triggering the loading spinner.
   *  Used after review submission so the "Saved" badge updates without showing
   *  the "Running Investigation" screen. */
  const refreshDetailSilent = async (id: string) => {
    try {
      const detail = await api.getInvestigation(id);
      setCurrentInvestigation(detail);
    } catch {
      // Non-critical: user already sees the submitted state; swallow quietly.
    }
  };

  useEffect(() => {
    void loadHistory();
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setIsNewModalOpen(true);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  useEffect(() => {
    if (!investigationId) {
      setCurrentInvestigation(null);
      return;
    }
    void loadDetail(investigationId);
  }, [investigationId]);

  const handleLaunchInvestigation = async (question: string) => {
    setIsNewModalOpen(false);
    setLoading(true);
    setGlobalError(null);
    setCurrentInvestigation(null);
    // Move to Console immediately so the operator sees the running state
    // (History/Settings/etc. do not render the investigation loader).
    navigate(routes.console);

    try {
      const result = await api.runInvestigation({ question, wait: true });
      setCurrentInvestigation(result);
      await loadHistory();
      navigate(routes.consoleInvestigation(result.id));
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Investigation failed to complete.";
      setGlobalError(message);
      navigate(routes.console);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const launchQuestion = (location.state as LaunchLocationState | null)?.launchQuestion;
    if (!launchQuestion || location.pathname !== routes.console) return;

    void (async () => {
      navigate(routes.console, { replace: true, state: null });
      await handleLaunchInvestigation(launchQuestion);
    })();
  }, [location.state, location.pathname, navigate]);

  const handleSubmitReview = async (payload: {
    decision: ReviewDecision;
    reviewer: string;
    notes?: string;
  }) => {
    if (!currentInvestigation) return;
    setSubmittingReview(true);
    setGlobalError(null);
    try {
      await api.submitReview(currentInvestigation.id, payload);
      // Use silent refresh — avoids triggering the full-page "Running Investigation" spinner
      await refreshDetailSilent(currentInvestigation.id);
      await loadHistory();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to submit operator review.";
      setGlobalError(message);
    } finally {
      setSubmittingReview(false);
    }
  };

  const handleSelectSource = (sourceId: string) => {
    if (!investigationId) return;
    setSelectedSourceId(sourceId);
    navigate(routes.consoleInvestigation(investigationId, "evidence"));
    setTimeout(() => {
      const el = document.getElementById(`source-${sourceId}`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }, 100);
  };

  const setActiveSubView = (view: ReturnType<typeof parseConsoleSubView>) => {
    if (!investigationId) return;
    if (view === "report") {
      navigate(routes.consoleInvestigation(investigationId));
      return;
    }
    navigate(routes.consoleInvestigation(investigationId, view));
  };

  const outletContext: AppShellOutletContext = {
    investigations,
    currentInvestigation,
    loading,
    submittingReview,
    activeSubView,
    selectedSourceId,
    approvedCount,
    loadDetail,
    handleLaunchInvestigation,
    handleSubmitReview,
    handleSelectSource,
    setActiveSubView,
    setSelectedSourceId,
    openNewInvestigationModal: () => setIsNewModalOpen(true),
    openAuditDrawer: () => setIsAuditDrawerOpen(true),
  };

  return (
    <div className="app-shell min-h-screen flex flex-col font-sans selection:bg-accent-500 selection:text-surface-950">
      <Header
        investigationCount={investigations.length}
        approvedCount={approvedCount}
        onNewInvestigationClick={() => setIsNewModalOpen(true)}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-6 pb-[max(1rem,env(safe-area-inset-bottom))] min-w-0">
        {notice && (
          <div className="mb-4 sm:mb-6 rounded-xl bg-rose-950/60 border border-rose-800 text-rose-100 shadow-lg animate-slide-up overflow-hidden">
            <div className="p-3.5 sm:p-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between min-w-0">
              <div className="flex items-start gap-2.5 min-w-0 flex-1">
                <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                <div className="min-w-0 space-y-1.5">
                  <p className="font-semibold text-sm text-rose-50">{notice.title}</p>
                  <p className="text-xs leading-relaxed text-rose-200/95 break-words">
                    {notice.body}
                  </p>
                  {notice.actionTo && notice.actionLabel ? (
                    <Link
                      to={notice.actionTo}
                      onClick={() => setGlobalError(null)}
                      className="inline-flex items-center gap-1.5 mt-1 text-xs font-medium text-accent-300 hover:text-accent-200 underline-offset-2 hover:underline"
                    >
                      {notice.actionLabel}
                      <ArrowRight className="w-3.5 h-3.5" />
                    </Link>
                  ) : null}
                </div>
              </div>
              <button
                type="button"
                onClick={() => setGlobalError(null)}
                className="self-end sm:self-start text-rose-400 hover:text-rose-200 text-xs font-medium shrink-0 px-2 py-1 rounded-md hover:bg-rose-900/40"
              >
                Dismiss
              </button>
            </div>
          </div>
        )}

        <Outlet context={outletContext} />
      </main>

      <NewInvestigationModal
        isOpen={isNewModalOpen}
        onClose={() => setIsNewModalOpen(false)}
        onSubmit={handleLaunchInvestigation}
        loading={loading}
      />

      <AuditDrawer
        isOpen={isAuditDrawerOpen}
        onClose={() => setIsAuditDrawerOpen(false)}
        audit={currentInvestigation?.audit || null}
      />
    </div>
  );
}
