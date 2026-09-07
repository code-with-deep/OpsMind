import { useState } from "react";
import { InvestigationSummaryItem } from "../../types";
import { formatDate, getStatusBadgeConfig } from "../../lib/utils";
import { ConfidenceMeter } from "../common/ConfidenceMeter";
import { Badge } from "../common/Badge";
import { Button } from "../common/Button";
import { PageHeader } from "../common/PageHeader";
import { EmptyState, FilterPills, ListCard, SearchBar } from "../common/AppUI";
import { History, PlayCircle, Brain, PlusCircle } from "lucide-react";

interface InvestigationListProps {
  investigations: InvestigationSummaryItem[];
  onSelectInvestigation: (id: string) => void;
  onNewClick: () => void;
  loading?: boolean;
}

const STATUS_FILTERS = [
  { key: "all", label: "All" },
  { key: "completed", label: "Completed" },
  { key: "approved", label: "Approved" },
  { key: "needs_clarification", label: "Clarify" },
  { key: "guardrail_rejected", label: "Blocked" },
];

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
    <div className="space-y-5">
      <PageHeader
        icon={<History className="w-5 h-5" />}
        title="Investigation History"
        description="Browse and replay past investigation runs"
        badge={
          <Badge variant="success" size="xs">
            {investigations.length} total
          </Badge>
        }
        action={
          <Button variant="accent" size="sm" icon={<PlusCircle className="w-4 h-4" />} onClick={onNewClick}>
            New Investigation
          </Button>
        }
      />

      <div className="flex flex-col sm:flex-row gap-3">
        <SearchBar
          value={search}
          onChange={setSearch}
          placeholder="Search by question or run ID..."
          className="flex-1"
        />
        <FilterPills options={STATUS_FILTERS} value={statusFilter} onChange={setStatusFilter} className="w-full sm:w-auto" />
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          icon={<History className="w-10 h-10" />}
          title="No investigations found"
          description="Try a different search or filter, or start a new investigation."
          action={
            <Button variant="accent" size="sm" onClick={onNewClick}>
              Start Investigation
            </Button>
          }
        />
      ) : (
        <div className="space-y-3">
          {filtered.map((item) => {
            const badgeCfg = getStatusBadgeConfig(item.status);
            return (
              <ListCard key={item.id} onClick={() => onSelectInvestigation(item.id)}>
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="space-y-2 flex-1 min-w-0">
                    <h3 className="font-app-heading text-base text-white leading-snug group-hover:text-accent-300 transition-colors">
                      {item.question}
                    </h3>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="app-stat-chip">#{item.id.slice(0, 8)}</span>
                      <span
                        className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[11px] font-medium border ${badgeCfg.className}`}
                      >
                        <span className={`w-1.5 h-1.5 rounded-full ${badgeCfg.dotColor}`} />
                        {badgeCfg.label}
                      </span>
                      {item.is_approved && (
                        <Badge variant="success" size="xs">
                          <Brain className="w-3 h-3 mr-1" />
                          In Case Memory
                        </Badge>
                      )}
                      <span className="text-xs text-surface-500">{formatDate(item.created_at)}</span>
                    </div>
                  </div>

                  <div className="flex flex-col xs:flex-row xs:items-center justify-between gap-3 w-full sm:w-auto">
                    <ConfidenceMeter value={item.confidence} size="sm" />
                    <Button
                      variant="outline"
                      size="sm"
                      className="w-full xs:w-auto"
                      icon={<PlayCircle className="w-3.5 h-3.5 text-accent-400" />}
                    >
                      Open
                    </Button>
                  </div>
                </div>
              </ListCard>
            );
          })}
        </div>
      )}
    </div>
  );
}
