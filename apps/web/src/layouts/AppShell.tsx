import { useEffect, useState } from "react";
import { Outlet, useLocation, useNavigate, useParams } from "react-router-dom";
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
import { AlertTriangle } from "lucide-react";

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
      await loadDetail(currentInvestigation.id);
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

      <main className="flex-1 max-w-7xl w-full mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-6 pb-[max(1rem,env(safe-area-inset-bottom))]">
        {globalError && (
          <div className="mb-4 sm:mb-6 p-3.5 sm:p-4 rounded-xl bg-rose-950/60 border border-rose-800 text-rose-200 text-xs flex items-start justify-between gap-3 shadow-lg animate-slide-up">
            <div className="flex items-start gap-2.5">
              <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold text-rose-100 block mb-0.5">
                  Execution / Guardrail Notice
                </span>
                <span className="leading-relaxed">{globalError}</span>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setGlobalError(null)}
              className="text-rose-400 hover:text-rose-200 text-xs font-mono shrink-0"
            >
              Dismiss
            </button>
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
