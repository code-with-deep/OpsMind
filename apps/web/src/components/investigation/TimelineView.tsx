import { useState } from "react";
import { InvestigationEvent } from "../../types";
import { formatDate } from "../../lib/utils";
import {
  Clock,
  ChevronDown,
  ChevronRight,
  ShieldAlert,
  Brain,
  Database,
  FileText,
  Sparkles,
  Scale,
  CheckCircle,
  MessageSquareCheck,
  Check,
  Copy,
} from "lucide-react";
import { Badge } from "../common/Badge";
import { EmptyState, SectionCard } from "../common/AppUI";

interface TimelineViewProps {
  events: InvestigationEvent[];
}

export function TimelineView({ events }: TimelineViewProps) {
  const [expandedIndices, setExpandedIndices] = useState<Record<number, boolean>>({});
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);

  const toggleExpand = (idx: number) => {
    setExpandedIndices((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

  const handleCopyPayload = (idx: number, payload: unknown, e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
    setCopiedIdx(idx);
    setTimeout(() => setCopiedIdx(null), 2000);
  };

  const getEventIcon = (type: string) => {
    if (type.includes("guardrail")) return <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />;
    if (type.includes("planner")) return <Brain className="w-3.5 h-3.5 text-indigo-400" />;
    if (type.includes("data_investigator")) return <Database className="w-3.5 h-3.5 text-sky-400" />;
    if (type.includes("knowledge")) return <FileText className="w-3.5 h-3.5 text-purple-400" />;
    if (type.includes("synthesizer")) return <Sparkles className="w-3.5 h-3.5 text-accent-400" />;
    if (type.includes("critic")) return <Scale className="w-3.5 h-3.5 text-amber-400" />;
    if (type.includes("review") || type.includes("case"))
      return <MessageSquareCheck className="w-3.5 h-3.5 text-emerald-400" />;
    return <CheckCircle className="w-3.5 h-3.5 text-surface-400" />;
  };

  const formatEventLabel = (type: string) =>
    type
      .replace(/_/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <SectionCard
      title="Execution Timeline"
      subtitle={`${events.length} agent events logged during this run`}
      icon={<Clock className="w-4 h-4" />}
      noPadding
    >
      <div className="p-4 sm:p-5 space-y-4 app-scroll-panel">
        {events.length === 0 ? (
          <EmptyState
            icon={<Clock className="w-8 h-8" />}
            title="No events yet"
            description="Agent events will appear here as the investigation runs."
          />
        ) : (
          events.map((event, idx) => {
            const isExpanded = expandedIndices[idx];
            const hasPayload = event.payload && Object.keys(event.payload).length > 0;

            return (
              <div key={idx} className="flex items-start gap-3">
                <div className="flex flex-col items-center shrink-0">
                  <div className="w-8 h-8 rounded-full app-card flex items-center justify-center">
                    {getEventIcon(event.event_type)}
                  </div>
                  {idx < events.length - 1 && (
                    <div className="w-px flex-1 min-h-[20px] bg-surface-800 my-1" />
                  )}
                </div>

                <div className="flex-1 app-card p-4 min-w-0">
                  <button
                    type="button"
                    className={`w-full flex items-center justify-between gap-2 text-left ${
                      hasPayload ? "cursor-pointer" : "cursor-default"
                    }`}
                    onClick={() => hasPayload && toggleExpand(idx)}
                  >
                    <div className="flex items-center gap-2 flex-wrap min-w-0">
                      <span className="text-sm font-medium text-white">
                        {formatEventLabel(event.event_type)}
                      </span>
                      <Badge variant="default" size="xs">
                        Step {idx + 1}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-xs text-surface-500">{formatDate(event.created_at)}</span>
                      {hasPayload &&
                        (isExpanded ? (
                          <ChevronDown className="w-4 h-4 text-surface-400" />
                        ) : (
                          <ChevronRight className="w-4 h-4 text-surface-400" />
                        ))}
                    </div>
                  </button>

                  {isExpanded && hasPayload && (
                    <div className="mt-3 pt-3 border-t border-surface-800/50 space-y-2">
                      <div className="flex items-center justify-between text-xs text-surface-400">
                        <span>Event payload</span>
                        <button
                          type="button"
                          onClick={(e) => handleCopyPayload(idx, event.payload, e)}
                          className="touch-target rounded-md hover:bg-surface-800 text-surface-400 hover:text-surface-200"
                          aria-label="Copy event payload"
                        >
                          {copiedIdx === idx ? (
                            <Check className="w-3 h-3 text-accent-400" />
                          ) : (
                            <Copy className="w-3 h-3" />
                          )}
                          Copy
                        </button>
                      </div>
                      <pre className="p-3 rounded-lg bg-surface-950 border border-surface-800 text-xs font-mono text-surface-300 overflow-x-auto max-h-48 leading-relaxed">
                        {JSON.stringify(event.payload, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </SectionCard>
  );
}
