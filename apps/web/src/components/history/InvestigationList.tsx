import { useState } from "react";
import { InvestigationSummaryItem } from "../../types";
import { formatDate, getStatusBadgeConfig } from "../../lib/utils";
import { ConfidenceMeter } from "../common/ConfidenceMeter";
import { Badge } from "../common/Badge";
import { Button } from "../common/Button";
import {
  History,
  Search,
  PlayCircle,
  Brain,
  PlusCircle,
} from "lucide-react";

interface InvestigationListProps {
  investigations: InvestigationSummaryItem[];
  onSelectInvestigation: (id: string) => void;
  onNewClick: () => void;
  loading?: boolean;
}

export function InvestigationList({
  investigations,
  onSelectInvestigation,
  onNewClick,
}: InvestigationListProps) {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const filtered = investigations.filter((item) => {
    if (statusFilter !== "all") {
      if (statusFilter === "approved" && !item.is_approved) return false;
      if (statusFilter !== "approved" && item.status !== statusFilter) return false;
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      return (
        item.question.toLowerCase().includes(q) ||
        item.id.toLowerCase().includes(q) ||
        item.status.toLowerCase().includes(q)
      );
    }
    return true;
  });

  return (
    <div className="space-y-4 sm:space-y-5">
      {/* Search & Filter Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-surface-900 border border-surface-800 p-4 sm:p-5 rounded-2xl shadow-sm">
        <div className="flex items-center gap-2.5 sm:gap-3 min-w-0">
          <div className="w-9 h-9 sm:w-10 sm:h-10 rounded-xl bg-brand-950 border border-brand-800 flex items-center justify-center text-brand-400 shrink-0">
            <History className="w-4 h-4 sm:w-5 sm:h-5" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="text-sm sm:text-base font-bold text-surface-100 truncate">
                Investigation History & Replay
              </h2>
              <Badge variant="brand" size="xs" className="shrink-0">
                {investigations.length} Runs
              </Badge>
            </div>
            <p className="text-[10px] sm:text-xs text-surface-400 mt-0.5 truncate">
              Persistent episodic memory replayable from Postgres checkpointer
            </p>
          </div>
        </div>

        <Button
          variant="primary"
          size="sm"
          icon={<PlusCircle className="w-4 h-4" />}
          onClick={onNewClick}
          className="self-start sm:self-center shrink-0"
        >
          New Investigation
        </Button>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5 sm:gap-3">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-surface-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search runs by question or Run ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-surface-900 border border-surface-750 rounded-xl text-xs sm:text-sm text-surface-100 placeholder:text-surface-500 focus:outline-none focus:border-brand-500"
          />
        </div>

        {/* Status Filter Tabs (Scrollable on mobile) */}
        <div className="flex items-center bg-surface-900 p-1 rounded-xl border border-surface-800 shrink-0 overflow-x-auto">
          {["all", "completed", "approved", "needs_clarification", "guardrail_rejected"].map(
            (statusKey) => (
              <button
                key={statusKey}
                type="button"
                onClick={() => setStatusFilter(statusKey)}
                className={`px-2.5 sm:px-3 py-1 text-[11px] sm:text-xs rounded-lg font-medium transition-all capitalize whitespace-nowrap shrink-0 ${
                  statusFilter === statusKey
                    ? "bg-brand-600 text-white shadow-sm"
                    : "text-surface-400 hover:text-surface-200"
                }`}
              >
                {statusKey === "all"
                  ? "All"
                  : statusKey === "needs_clarification"
                  ? "Clarify"
                  : statusKey === "guardrail_rejected"
                  ? "Guardrail"
                  : statusKey}
              </button>
            )
          )}
        </div>
      </div>

      {/* Investigations List */}
      {filtered.length === 0 ? (
        <div className="p-8 sm:p-12 text-center bg-surface-900/60 border border-surface-800 rounded-2xl space-y-3">
          <History className="w-8 h-8 sm:w-10 sm:h-10 text-surface-600 mx-auto" />
          <h3 className="text-xs sm:text-sm font-semibold text-surface-200">No Investigations Found</h3>
          <p className="text-[11px] sm:text-xs text-surface-400 max-w-sm mx-auto">
            Try adjusting your search criteria or launch a new investigation to start gathering evidence.
          </p>
        </div>
      ) : (
        <div className="space-y-2.5 sm:space-y-3">
          {filtered.map((item) => {
            const badgeCfg = getStatusBadgeConfig(item.status);
            return (
              <div
                key={item.id}
                onClick={() => onSelectInvestigation(item.id)}
                className="p-3.5 sm:p-5 rounded-2xl bg-surface-900 border border-surface-800 hover:border-surface-700 transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-3 sm:gap-4 cursor-pointer group shadow-sm"
              >
                <div className="space-y-1.5 sm:space-y-2 flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[10px] sm:text-[11px] font-mono text-surface-400">
                      ID: {item.id.slice(0, 8)}...
                    </span>
                    <span
                      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] sm:text-[11px] font-medium border ${badgeCfg.className}`}
                    >
                      <span className={`w-1.5 h-1.5 rounded-full ${badgeCfg.dotColor}`} />
                      {badgeCfg.label}
                    </span>
                    {item.is_approved && (
                      <Badge variant="success" size="xs">
                        <Brain className="w-3 h-3 text-emerald-400 mr-1" />
                        Case Memory
                      </Badge>
                    )}
                    <span className="text-[10px] sm:text-[11px] text-surface-500 font-mono">
                      {formatDate(item.created_at)}
                    </span>
                  </div>

                  <h3 className="text-xs sm:text-sm font-semibold text-surface-100 group-hover:text-brand-300 transition-colors leading-snug break-words">
                    {item.question}
                  </h3>
                </div>

                <div className="flex items-center gap-3 sm:shrink-0 pt-2 sm:pt-0 border-t sm:border-t-0 border-surface-800 justify-between sm:justify-end">
                  <ConfidenceMeter value={item.confidence} size="sm" />
                  <Button
                    variant="outline"
                    size="xs"
                    icon={<PlayCircle className="w-3.5 h-3.5 text-brand-400" />}
                  >
                    Open
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
