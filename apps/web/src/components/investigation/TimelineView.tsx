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

interface TimelineViewProps {
  events: InvestigationEvent[];
}

export function TimelineView({ events }: TimelineViewProps) {
  const [expandedIndices, setExpandedIndices] = useState<Record<number, boolean>>({});
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);

  const toggleExpand = (idx: number) => {
    setExpandedIndices((prev) => ({
      ...prev,
      [idx]: !prev[idx],
    }));
  };

  const handleCopyPayload = (idx: number, payload: any, e: React.MouseEvent) => {
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
    if (type.includes("synthesizer")) return <Sparkles className="w-3.5 h-3.5 text-brand-400" />;
    if (type.includes("critic")) return <Scale className="w-3.5 h-3.5 text-amber-400" />;
    if (type.includes("review") || type.includes("case")) return <MessageSquareCheck className="w-3.5 h-3.5 text-emerald-400" />;
    return <CheckCircle className="w-3.5 h-3.5 text-surface-400" />;
  };

  return (
    <div className="bg-surface-900 border border-surface-800 rounded-2xl overflow-hidden flex flex-col shadow-sm">
      <div className="p-4 sm:p-5 border-b border-surface-800 flex items-center justify-between shrink-0 gap-2">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-8 h-8 rounded-lg bg-purple-950 border border-purple-800 flex items-center justify-center text-purple-400 shrink-0">
            <Clock className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <h3 className="text-xs sm:text-base font-semibold text-surface-100 truncate">
              Execution Event Log & Telemetry ({events.length})
            </h3>
            <p className="text-[10px] sm:text-[11px] text-surface-400 truncate">
              Sequential graph telemetry captured in Postgres memory store
            </p>
          </div>
        </div>

        <Badge variant="purple" size="xs" className="shrink-0">
          Telemetry
        </Badge>
      </div>

      <div className="p-3.5 sm:p-5 overflow-y-auto space-y-3 max-h-[650px]">
        {events.length === 0 ? (
          <div className="text-center py-12 text-surface-500 text-xs">
            No telemetry events logged for this investigation.
          </div>
        ) : (
          events.map((event, idx) => {
            const isExpanded = expandedIndices[idx];
            const hasPayload =
              event.payload && Object.keys(event.payload).length > 0;

            return (
              <div
                key={idx}
                className="flex items-start gap-2.5 sm:gap-3 text-xs group transition-all"
              >
                {/* Timeline icon & vertical line */}
                <div className="flex flex-col items-center shrink-0 mt-0.5">
                  <div className="w-6 h-6 sm:w-7 sm:h-7 rounded-full bg-surface-950 border border-surface-700 flex items-center justify-center shadow-inner">
                    {getEventIcon(event.event_type)}
                  </div>
                  {idx < events.length - 1 && (
                    <div className="w-px h-full bg-surface-800 my-1 min-h-[16px] sm:min-h-[20px]" />
                  )}
                </div>

                {/* Event Card */}
                <div
                  className={`flex-1 rounded-xl border p-3 sm:p-3.5 transition-all select-none min-w-0 ${
                    isExpanded
                      ? "bg-surface-950 border-surface-700 shadow-sm"
                      : "bg-surface-950/70 border-surface-800/90 hover:border-surface-750"
                  }`}
                >
                  <div
                    className={`flex items-center justify-between gap-2 ${
                      hasPayload ? "cursor-pointer" : ""
                    }`}
                    onClick={() => hasPayload && toggleExpand(idx)}
                  >
                    <div className="flex items-center gap-1.5 sm:gap-2 flex-wrap min-w-0">
                      <span className="font-mono font-semibold text-surface-200 text-xs truncate">
                        {event.event_type}
                      </span>
                      <Badge variant="default" size="xs">
                        #{idx + 1}
                      </Badge>
                    </div>

                    <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
                      <span className="text-[10px] text-surface-400 font-mono">
                        {formatDate(event.created_at)}
                      </span>
                      {hasPayload && (
                        <button
                          type="button"
                          className="text-surface-400 hover:text-surface-200 p-0.5"
                          aria-label="Toggle state payload"
                        >
                          {isExpanded ? (
                            <ChevronDown className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                          ) : (
                            <ChevronRight className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                          )}
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Expanded JSON payload preview */}
                  {isExpanded && hasPayload && (
                    <div className="mt-3 pt-3 border-t border-surface-850 space-y-2 animate-fadeIn">
                      <div className="flex items-center justify-between text-[10px] font-mono text-surface-400">
                        <span>Event State Payload</span>
                        <button
                          type="button"
                          onClick={(e) => handleCopyPayload(idx, event.payload, e)}
                          className="text-surface-400 hover:text-surface-200 flex items-center gap-1"
                        >
                          {copiedIdx === idx ? (
                            <Check className="w-3 h-3 text-emerald-400" />
                          ) : (
                            <Copy className="w-3 h-3" />
                          )}
                          <span>{copiedIdx === idx ? "Copied" : "Copy JSON"}</span>
                        </button>
                      </div>
                      <pre className="p-2.5 sm:p-3 rounded-lg bg-surface-900 border border-surface-800 text-[10px] sm:text-[11px] font-mono text-surface-300 overflow-x-auto max-h-48 leading-relaxed">
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
    </div>
  );
}
