import { useOutletContext } from "react-router-dom";
import { AppShellOutletContext } from "../layouts/AppShell";
import { LiveDAGView } from "../components/investigation/LiveDAGView";
import { ReportView } from "../components/investigation/ReportView";
import { EvidenceExplorer } from "../components/investigation/EvidenceExplorer";
import { TimelineView } from "../components/investigation/TimelineView";
import { ReviewPanel } from "../components/investigation/ReviewPanel";
import { Badge } from "../components/common/Badge";
import { Button } from "../components/common/Button";
import { SubViewTabs } from "../components/common/AppUI";
import { getStatusBadgeConfig } from "../lib/utils";
import { Clock, Layers, PlusCircle, RotateCw, Sparkles } from "lucide-react";

export function ConsolePage() {
  const {
    currentInvestigation,
    loading,
    activeSubView,
    selectedSourceId,
    submittingReview,
    handleSubmitReview,
    handleSelectSource,
    setActiveSubView,
    setSelectedSourceId,
    openNewInvestigationModal,
    openAuditDrawer,
  } = useOutletContext<AppShellOutletContext>();

  if (loading) {
    return (
      <div className="animate-fadeIn">
        <div className="app-card p-10 sm:p-16 text-center space-y-4">
          <div className="w-12 h-12 rounded-2xl bg-accent-950 border border-accent-800 flex items-center justify-center mx-auto text-accent-400 shadow-glow-accent">
            <RotateCw className="w-6 h-6 animate-spin" />
          </div>
          <h3 className="font-app-heading text-lg text-white">Running Investigation</h3>
          <p className="text-sm text-surface-400 max-w-md mx-auto leading-relaxed">
            Agents are gathering SQL evidence, retrieving playbooks, and synthesizing a
            grounded report. This usually takes a few seconds.
          </p>
        </div>
      </div>
    );
  }

  if (!currentInvestigation) {
    return (
      <div className="animate-fadeIn">
        <div className="app-card p-10 sm:p-16 text-center space-y-4">
          <Sparkles className="w-10 h-10 mx-auto text-accent-400" />
          <h3 className="font-app-heading text-lg text-white">No Investigation Selected</h3>
          <p className="text-sm text-surface-400 max-w-md mx-auto leading-relaxed">
            Start a new investigation or pick a past run from History to view its report,
            evidence, and timeline.
          </p>
          <Button
            variant="accent"
            size="md"
            icon={<PlusCircle className="w-4 h-4" />}
            onClick={openNewInvestigationModal}
          >
            Start Investigation
          </Button>
        </div>
      </div>
    );
  }

  const findingCount = currentInvestigation.findings?.length || 0;
  const timelineCount = currentInvestigation.timeline?.length || 0;

  return (
    <div className="space-y-5 sm:space-y-6 animate-fadeIn">
      {/* Investigation header */}
      <div className="app-panel p-5 sm:p-6 space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="app-stat-chip">
            ID {currentInvestigation.id.slice(0, 8)}
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
          {currentInvestigation.confidence != null && (
            <span className="app-stat-chip text-accent-400">
              {Math.round(currentInvestigation.confidence * 100)}% confidence
            </span>
          )}
        </div>

        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
          <h1 className="font-app-heading text-xl sm:text-2xl text-white leading-snug break-words flex-1">
            {currentInvestigation.question}
          </h1>
          <Button variant="secondary" size="sm" onClick={openNewInvestigationModal} className="shrink-0">
            New Run
          </Button>
        </div>
      </div>

      <LiveDAGView investigation={currentInvestigation} />

      <SubViewTabs
        active={activeSubView}
        onChange={(key) => setActiveSubView(key as typeof activeSubView)}
        tabs={[
          { key: "report", label: "Report", icon: <Sparkles className="w-3.5 h-3.5" /> },
          { key: "evidence", label: "Evidence", icon: <Layers className="w-3.5 h-3.5" />, count: findingCount },
          { key: "timeline", label: "Timeline", icon: <Clock className="w-3.5 h-3.5" />, count: timelineCount },
        ]}
      />

      {activeSubView === "report" && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 sm:gap-6 items-start">
          <div className="md:col-span-2">
            <ReportView
              investigation={currentInvestigation}
              onSelectSource={handleSelectSource}
              onAuditClick={openAuditDrawer}
            />
          </div>
          <div className="md:col-span-1">
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
    </div>
  );
}
