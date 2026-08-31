import { useEffect, useState } from "react";
import {
  InvestigationDetail,
  InvestigationSummaryItem,
  ReviewDecision,
} from "./types";
import { api } from "./lib/api";
import { Header, ActiveTab } from "./components/layout/Header";
import { LandingPage } from "./components/landing/LandingPage";
import { LiveDAGView } from "./components/investigation/LiveDAGView";
import { ReportView } from "./components/investigation/ReportView";
import { EvidenceExplorer } from "./components/investigation/EvidenceExplorer";
import { TimelineView } from "./components/investigation/TimelineView";
import { ReviewPanel } from "./components/investigation/ReviewPanel";
import { AuditDrawer } from "./components/investigation/AuditDrawer";
import { NewInvestigationModal } from "./components/investigation/NewInvestigationModal";
import { InvestigationList } from "./components/history/InvestigationList";
import { CaseMemoryCatalog } from "./components/cases/CaseMemoryCatalog";
import { ToolsDirectLab } from "./components/tools/ToolsDirectLab";
import { Badge } from "./components/common/Badge";
import { Button } from "./components/common/Button";
import { getStatusBadgeConfig } from "./lib/utils";
import {
  AlertTriangle,
  Clock,
  Layers,
  Sparkles,
  PlusCircle,
  RotateCw,
} from "lucide-react";

export function App() {
  const [activeTab, setActiveTab] = useState<ActiveTab>("overview");
  const [investigations, setInvestigations] = useState<InvestigationSummaryItem[]>([]);
  const [currentInvestigation, setCurrentInvestigation] =
    useState<InvestigationDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [isNewModalOpen, setIsNewModalOpen] = useState(false);
  const [isAuditDrawerOpen, setIsAuditDrawerOpen] = useState(false);
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);
  const [activeSubView, setActiveSubView] = useState<"report" | "evidence" | "timeline">(
    "report"
  );
  const [submittingReview, setSubmittingReview] = useState(false);
  const [globalError, setGlobalError] = useState<string | null>(null);

  // Load history on mount
  const loadHistory = async () => {
    try {
      const res = await api.listInvestigations();
      setInvestigations(res.investigations || []);
      // If no current investigation is selected, set latest for the console
      if (!currentInvestigation && res.investigations?.length > 0) {
        loadDetail(res.investigations[0].id);
      }
    } catch (err: any) {
      console.warn("History load error:", err.message);
    }
  };

  const loadDetail = async (id: string) => {
    setLoading(true);
    setGlobalError(null);
    try {
      const detail = await api.getInvestigation(id);
      setCurrentInvestigation(detail);
    } catch (err: any) {
      setGlobalError(err.message || "Failed to load investigation details.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadHistory();
  }, []);

  // Global keyboard shortcuts (Cmd+K / Ctrl+K for new investigation)
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

  // Launch investigation
  const handleLaunchInvestigation = async (question: string) => {
    setIsNewModalOpen(false);
    setLoading(true);
    setGlobalError(null);
    setActiveTab("investigation");
    setActiveSubView("report");

    try {
      const result = await api.runInvestigation({ question, wait: true });
      setCurrentInvestigation(result);
      await loadHistory();
    } catch (err: any) {
      setGlobalError(err.message || "Investigation failed to complete.");
    } finally {
      setLoading(false);
    }
  };

  // Submit human review
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
    } catch (err: any) {
      setGlobalError(err.message || "Failed to submit operator review.");
    } finally {
      setSubmittingReview(false);
    }
  };

  const handleSelectSource = (sourceId: string) => {
    setSelectedSourceId(sourceId);
    setActiveSubView("evidence");
    setTimeout(() => {
      const el = document.getElementById(`source-${sourceId}`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }, 100);
  };

  const approvedCount = investigations.filter((i) => i.is_approved).length;

  return (
    <div className="min-h-screen bg-surface-950 text-surface-100 flex flex-col font-sans selection:bg-brand-500 selection:text-white">
      {/* Top Application Header */}
      <Header
        activeTab={activeTab}
        onTabChange={setActiveTab}
        onNewInvestigationClick={() => setIsNewModalOpen(true)}
        investigationCount={investigations.length}
        approvedCount={approvedCount}
      />

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-6">
        {/* Global Error Banner */}
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

        {/* Tab 0: Product Overview & Highlights Landing Page */}
        {activeTab === "overview" && (
          <LandingPage
            onLaunchConsole={() => setActiveTab("investigation")}
            onSelectScenario={handleLaunchInvestigation}
            onExploreHistory={() => setActiveTab("history")}
            onExploreCases={() => setActiveTab("cases")}
            onExploreTools={() => setActiveTab("tools")}
            investigationCount={investigations.length}
            approvedCount={approvedCount}
          />
        )}

        {/* Tab 1: Live Investigation Console */}
        {activeTab === "investigation" && (
          <div className="space-y-4 sm:space-y-6 animate-fadeIn">
            {loading ? (
              <div className="bg-surface-900 border border-surface-800 rounded-2xl p-8 sm:p-16 text-center space-y-4 shadow-sm">
                <div className="w-12 h-12 rounded-2xl bg-brand-950 border border-brand-800 flex items-center justify-center mx-auto text-brand-400 shadow-glow-sm">
                  <RotateCw className="w-6 h-6 animate-spin" />
                </div>
                <h3 className="text-sm sm:text-base font-semibold text-surface-100">
                  Executing LangGraph Multi-Agent Investigation...
                </h3>
                <p className="text-[11px] sm:text-xs text-surface-400 max-w-md mx-auto leading-relaxed">
                  Planner triage $\rightarrow$ Allowlisted SQL queries $\rightarrow$ Playbook pgvector RAG $\rightarrow$ Synthesizer hypothesis $\rightarrow$ Critic verification loop.
                </p>
              </div>
            ) : !currentInvestigation ? (
              <div className="bg-surface-900 border border-surface-800 rounded-2xl p-8 sm:p-16 text-center space-y-4 shadow-sm">
                <Sparkles className="w-10 h-10 mx-auto text-brand-400 mb-2" />
                <h3 className="text-sm sm:text-base font-semibold text-surface-100">
                  No Active Investigation Selected
                </h3>
                <p className="text-xs text-surface-400 max-w-md mx-auto">
                  Launch a new investigation with preloaded incident scenarios or choose a past run from history to replay.
                </p>
                <div className="pt-2">
                  <Button
                    variant="brand"
                    size="md"
                    icon={<PlusCircle className="w-4 h-4" />}
                    onClick={() => setIsNewModalOpen(true)}
                  >
                    Start Investigation
                  </Button>
                </div>
              </div>
            ) : (
              <>
                {/* Active Investigation Top Header Card */}
                <div className="bg-surface-900 border border-surface-800 rounded-2xl p-4 sm:p-6 shadow-sm space-y-3">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="space-y-1.5 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-[10px] sm:text-[11px] font-mono text-surface-400">
                          Run ID: {currentInvestigation.id.slice(0, 8)}...
                        </span>
                        <Badge
                          variant={
                            currentInvestigation.status === "completed"
                              ? "success"
                              : currentInvestigation.status === "guardrail_rejected"
                              ? "error"
                              : currentInvestigation.status === "needs_clarification"
                              ? "warning"
                              : "default"
                          }
                          size="xs"
                          dot
                        >
                          {getStatusBadgeConfig(currentInvestigation.status).label}
                        </Badge>
                      </div>
                      <h1 className="text-sm sm:text-lg md:text-xl font-bold text-surface-100 leading-snug break-words">
                        {currentInvestigation.question}
                      </h1>
                    </div>

                    <div className="flex items-center gap-2 shrink-0 self-start sm:self-center">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setIsNewModalOpen(true)}
                      >
                        New Run
                      </Button>
                    </div>
                  </div>
                </div>

                {/* 6-Agent Visual DAG Flow */}
                <LiveDAGView investigation={currentInvestigation} />

                {/* Sub-view Navigation Tabs (Report / Evidence / Timeline) */}
                <div className="flex items-center justify-between border-b border-surface-800 pb-2 overflow-x-auto">
                  <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
                    <button
                      type="button"
                      onClick={() => setActiveSubView("report")}
                      className={`flex items-center gap-1.5 sm:gap-2 px-3 sm:px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all shrink-0 ${
                        activeSubView === "report"
                          ? "bg-surface-800 text-surface-100 border border-surface-700 shadow-sm"
                          : "text-surface-400 hover:text-surface-200"
                      }`}
                    >
                      <Sparkles className="w-3.5 h-3.5 text-brand-400" />
                      <span>Report & Actions</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => setActiveSubView("evidence")}
                      className={`flex items-center gap-1.5 sm:gap-2 px-3 sm:px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all shrink-0 ${
                        activeSubView === "evidence"
                          ? "bg-surface-800 text-surface-100 border border-surface-700 shadow-sm"
                          : "text-surface-400 hover:text-surface-200"
                      }`}
                    >
                      <Layers className="w-3.5 h-3.5 text-sky-400" />
                      <span>Evidence ({currentInvestigation.findings?.length || 0})</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => setActiveSubView("timeline")}
                      className={`flex items-center gap-1.5 sm:gap-2 px-3 sm:px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all shrink-0 ${
                        activeSubView === "timeline"
                          ? "bg-surface-800 text-surface-100 border border-surface-700 shadow-sm"
                          : "text-surface-400 hover:text-surface-200"
                      }`}
                    >
                      <Clock className="w-3.5 h-3.5 text-purple-400" />
                      <span>Timeline ({currentInvestigation.timeline?.length || 0})</span>
                    </button>
                  </div>
                </div>

                {/* Active Sub-view Panels */}
                {activeSubView === "report" && (
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 sm:gap-6 items-start">
                    <div className="lg:col-span-2 space-y-5 sm:space-y-6">
                      <ReportView
                        investigation={currentInvestigation}
                        onSelectSource={handleSelectSource}
                        onAuditClick={() => setIsAuditDrawerOpen(true)}
                      />
                    </div>
                    <div className="lg:col-span-1 space-y-5 sm:space-y-6">
                      <ReviewPanel
                        investigation={currentInvestigation}
                        onSubmitReview={handleSubmitReview}
                        loading={submittingReview}
                      />
                    </div>
                  </div>
                )}

                {activeSubView === "evidence" && (
                  <EvidenceExplorer
                    findings={currentInvestigation.findings || []}
                    selectedSourceId={selectedSourceId}
                    onSelectSource={setSelectedSourceId}
                  />
                )}

                {activeSubView === "timeline" && (
                  <TimelineView events={currentInvestigation.timeline || []} />
                )}
              </>
            )}
          </div>
        )}

        {/* Tab 2: Investigation History */}
        {activeTab === "history" && (
          <div className="animate-fadeIn">
            <InvestigationList
              investigations={investigations}
              onSelectInvestigation={(id) => {
                loadDetail(id);
                setActiveTab("investigation");
                setActiveSubView("report");
              }}
              onNewClick={() => setIsNewModalOpen(true)}
            />
          </div>
        )}

        {/* Tab 3: Case Memory Catalog */}
        {activeTab === "cases" && (
          <div className="animate-fadeIn">
            <CaseMemoryCatalog
              onSelectInvestigation={(id) => {
                loadDetail(id);
                setActiveTab("investigation");
                setActiveSubView("report");
              }}
            />
          </div>
        )}

        {/* Tab 4: Allowlisted Tools Direct Lab */}
        {activeTab === "tools" && (
          <div className="animate-fadeIn">
            <ToolsDirectLab />
          </div>
        )}
      </main>

      {/* New Investigation Dialog */}
      <NewInvestigationModal
        isOpen={isNewModalOpen}
        onClose={() => setIsNewModalOpen(false)}
        onSubmit={handleLaunchInvestigation}
        loading={loading}
      />

      {/* Cryptographic Audit Drawer Dialog */}
      <AuditDrawer
        isOpen={isAuditDrawerOpen}
        onClose={() => setIsAuditDrawerOpen(false)}
        audit={currentInvestigation?.audit || null}
      />
    </div>
  );
}
