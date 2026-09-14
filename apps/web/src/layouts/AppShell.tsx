import { useCallback, useEffect, useRef, useState } from "react";
import { Link, Outlet, useLocation, useNavigate, useParams } from "react-router-dom";
import {
  InvestigationDetail,
  InvestigationSummaryItem,
  ReviewDecision,
} from "../types";
import { api, errorMessage, OnboardingStatus } from "../lib/api";
import { Header } from "../components/layout/Header";
import { AuditDrawer } from "../components/investigation/AuditDrawer";
import { NewInvestigationModal } from "../components/investigation/NewInvestigationModal";
import { useLiveRefresh, useRealtimeState } from "../hooks/useRealtime";
import { parseConsoleSubView, routes } from "../lib/routes";
import { AlertTriangle, ArrowRight } from "lucide-react";

export interface AppShellOutletContext {
  investigations: InvestigationSummaryItem[];
  currentInvestigation: InvestigationDetail | null;
  /** Loading a different investigation's details (not a background refresh). */
  loading: boolean;
  /** A new investigation is being started. */
  launching: boolean;
  submittingReview: boolean;
  activeSubView: ReturnType<typeof parseConsoleSubView>;
  selectedSourceId: string | null;
  approvedCount: number;
  loadDetail: (id: string) => Promise<void>;
  handleLaunchInvestigation: (question: string) => Promise<void>;
  handleSubmitReview: (payload: {
    decision: ReviewDecision;
    notes?: string;
  }) => Promise<void>;
  handleSelectSource: (sourceId: string) => void;
  setActiveSubView: (view: ReturnType<typeof parseConsoleSubView>) => void;
  setSelectedSourceId: (id: string | null) => void;
  openNewInvestigationModal: () => void;
  openAuditDrawer: () => void;
  /** Setup progress for the get-started checklist; null until loaded. */
  onboarding: OnboardingStatus | null;
  refreshOnboarding: () => Promise<void>;
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
  if (lower.includes("both company csv")) {
    return {
      title: "Business data and playbooks required",
      body: "Upload your company data ZIP (products.csv, orders.csv, order_items.csv) and at least one SOP playbook in Settings before running investigations.",
      actionTo: routes.settings,
      actionLabel: "Go to Settings",
    };
  }
  if (lower.includes("sop playbook")) {
    return {
      title: "Playbook required",
      body: "Upload at least one SOP playbook (Markdown or a .zip of them) in Settings before running investigations.",
      actionTo: routes.settings,
      actionLabel: "Go to Settings",
    };
  }
  if (
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
  if (lower.includes("guardrail") || lower.includes("jailbreak") || lower.includes("injection")) {
    return {
      title: "Question flagged",
      body: "Your question was flagged as potentially unsafe. Please rephrase it as an operations question — avoid instructions, code, or requests for credentials.",
    };
  }

  if (lower.includes("daily limit")) {
    return { title: "Daily limit reached", body: text };
  }

  // ── Auth ──────────────────────────────────────────────────────────────────
  if (lower.includes("session has expired") || lower.includes("sign in again")) {
    return {
      title: "Session expired",
      body: "Your session has expired. Please sign in again to continue.",
      actionTo: routes.login,
      actionLabel: "Sign in",
    };
  }

  if (lower.includes("permission") || lower.includes("only workspace admins")) {
    return { title: "Access denied", body: text };
  }

  // ── Network / server ──────────────────────────────────────────────────────
  if (lower.includes("can't reach the opsmind server")) {
    return { title: "Connection problem", body: text };
  }

  // ── Generic fallback ──────────────────────────────────────────────────────
  return {
    title: "Something went wrong",
    body: text || "An unexpected error occurred. Please try again.",
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
  const [launching, setLaunching] = useState(false);
  const [isNewModalOpen, setIsNewModalOpen] = useState(false);
  const [isAuditDrawerOpen, setIsAuditDrawerOpen] = useState(false);
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);
  const [submittingReview, setSubmittingReview] = useState(false);
  const [globalError, setGlobalError] = useState<string | null>(null);
  const notice = globalError ? toAppNotice(globalError) : null;
  const liveState = useRealtimeState();
  const [onboarding, setOnboarding] = useState<OnboardingStatus | null>(null);

  // The investigation the route currently asks for; responses for any other id
  // (e.g. a slow fetch after the user clicked elsewhere) are discarded.
  const requestedIdRef = useRef<string | null>(investigationId ?? null);
  const currentRef = useRef(currentInvestigation);
  currentRef.current = currentInvestigation;

  const activeSubView = parseConsoleSubView(subView);
  const approvedCount = investigations.filter((i) => i.is_approved).length;

  const loadHistory = useCallback(async () => {
    try {
      const res = await api.listInvestigations();
      setInvestigations(res.investigations || []);
    } catch (err: unknown) {
      console.warn("History load error:", errorMessage(err, "History load failed"));
    }
  }, []);

  const loadDetail = async (id: string) => {
    requestedIdRef.current = id;
    // Re-fetching the investigation already on screen shouldn't flash the loader.
    const showSpinner = currentRef.current?.id !== id;
    if (showSpinner) setLoading(true);
    setGlobalError(null);
    try {
      const detail = await api.getInvestigation(id);
      if (requestedIdRef.current === id) setCurrentInvestigation(detail);
    } catch (err: unknown) {
      if (requestedIdRef.current === id) {
        setGlobalError(errorMessage(err, "Couldn't load this investigation. Please try again."));
      }
    } finally {
      if (showSpinner) setLoading(false);
    }
  };

  /** Refresh the open investigation in place (live updates, after a review). */
  const refreshDetailSilent = async (id: string) => {
    try {
      const detail = await api.getInvestigation(id);
      if (requestedIdRef.current === id) setCurrentInvestigation(detail);
    } catch {
      // Non-critical: the next live update or fallback poll retries.
    }
  };

  const loadOnboarding = useCallback(async () => {
    try {
      setOnboarding(await api.getOnboardingStatus());
    } catch {
      // Non-critical: the checklist stays hidden and investigations still validate server-side.
    }
  }, []);

  useEffect(() => {
    void loadHistory();
    void loadOnboarding();
  }, [loadHistory, loadOnboarding]);

  // ── Live updates ──────────────────────────────────────────────────────────
  useLiveRefresh(["investigations", "reviews", "case_summaries"], () => void loadHistory(), {
    debounceMs: 500,
  });

  // Checklist steps tick off as uploads, runs, reviews and invites happen anywhere.
  useLiveRefresh(
    ["ingest_jobs", "documents", "investigations", "reviews", "invite_codes", "users"],
    () => void loadOnboarding(),
    { debounceMs: 800 }
  );

  useLiveRefresh(
    ["investigations", "investigation_events", "reviews", "case_summaries"],
    (events) => {
      const id = requestedIdRef.current;
      if (!id) return;
      const touchesCurrent =
        events.length === 0 || events.some((e) => e.id === id || e.investigation_id === id);
      if (touchesCurrent) void refreshDetailSilent(id);
    },
    { enabled: Boolean(investigationId), debounceMs: 250 }
  );

  // Fallback while the live connection is down: poll only a run still in progress.
  const isRunning = currentInvestigation?.status === "running";
  useEffect(() => {
    if (!investigationId || !isRunning || liveState === "live") return;
    const timer = setInterval(() => void refreshDetailSilent(investigationId), 4_000);
    return () => clearInterval(timer);
  }, [investigationId, isRunning, liveState]);

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
      requestedIdRef.current = null;
      setCurrentInvestigation(null);
      return;
    }
    void loadDetail(investigationId);
  }, [investigationId]);

  const handleLaunchInvestigation = async (question: string) => {
    setLaunching(true);
    setGlobalError(null);
    try {
      // Returns immediately with the run in `running` state; the console then
      // follows each agent live through the event stream.
      const started = await api.runInvestigation({ question });
      requestedIdRef.current = started.id;
      setCurrentInvestigation(started);
      setIsNewModalOpen(false);
      navigate(routes.consoleInvestigation(started.id));
      void loadHistory();
    } catch (err: unknown) {
      setIsNewModalOpen(false);
      setGlobalError(errorMessage(err, "Couldn't start the investigation. Please try again."));
      if (!investigationId) navigate(routes.console);
    } finally {
      setLaunching(false);
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
    notes?: string;
  }) => {
    if (!currentInvestigation) return;
    setSubmittingReview(true);
    setGlobalError(null);
    try {
      await api.submitReview(currentInvestigation.id, payload);
      await refreshDetailSilent(currentInvestigation.id);
      void loadHistory();
    } catch (err: unknown) {
      setGlobalError(errorMessage(err, "Couldn't save your review. Please try again."));
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
    launching,
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
    onboarding,
    refreshOnboarding: loadOnboarding,
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
          <div
            role="alert"
            className="mb-4 sm:mb-6 rounded-xl bg-rose-950/60 border border-rose-800 text-rose-100 shadow-lg animate-slide-up overflow-hidden"
          >
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
        loading={launching}
        onboarding={onboarding}
        onShowSetup={() => {
          setIsNewModalOpen(false);
          navigate(routes.console);
        }}
      />

      <AuditDrawer
        isOpen={isAuditDrawerOpen}
        onClose={() => setIsAuditDrawerOpen(false)}
        audit={currentInvestigation?.audit || null}
      />
    </div>
  );
}
