import {
  Brain,
  CheckCircle2,
  Database,
  FileText,
  RotateCw,
  Scale,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Zap,
} from "lucide-react";
import { InvestigationDetail } from "../../types";
import { Badge } from "../common/Badge";

interface LiveDAGViewProps {
  investigation: InvestigationDetail;
}

export function LiveDAGView({ investigation }: LiveDAGViewProps) {
  const nodeTrace = investigation.run?.node_trace || [];
  const status = investigation.status;
  const isRunning = status === "running";
  const retryCount = investigation.retry_count || 0;
  const sqlCount = investigation.findings?.filter((f) => f.source_id.startsWith("sql_")).length || 0;
  const ragCount = investigation.findings?.filter((f) => f.source_id.startsWith("rag_")).length || 0;

  const hasExecuted = (nodeKey: string) => {
    if (nodeTrace.includes(nodeKey)) return true;
    if (status === "completed") return true;
    if (
      status === "insufficient_evidence" &&
      ["planner", "data_investigator", "knowledge", "synthesizer", "critic"].includes(nodeKey)
    )
      return true;
    return false;
  };

  const isNodeActive = (nodeKey: string) => {
    if (!isRunning) return false;
    const lastNode = nodeTrace[nodeTrace.length - 1];
    return lastNode === nodeKey;
  };

  return (
    <div className="bg-surface-900/90 border border-surface-800 rounded-2xl p-4 sm:p-6 shadow-sm space-y-3.5 sm:space-y-4">
      {/* Top Meta Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 pb-3 border-b border-surface-800/80">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-brand-950/80 border border-brand-800/80 flex items-center justify-center text-brand-400 shrink-0">
            <Zap className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <h3 className="text-xs sm:text-sm font-semibold text-surface-100 truncate">
              LangGraph Multi-Agent Execution State
            </h3>
            <p className="text-[10px] sm:text-[11px] text-surface-400 truncate">
              Deterministic state machine with conditional Critic self-correction loop
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5 sm:gap-2 flex-wrap text-xs">
          {retryCount > 0 && (
            <span className="px-2 sm:px-2.5 py-0.5 rounded-full bg-amber-950/80 border border-amber-800 text-amber-300 font-mono text-[10px] sm:text-[11px] flex items-center gap-1.5 shadow-sm">
              <RotateCw className="w-3 h-3 animate-spin text-amber-400" />
              <span>Retries: {retryCount}/2</span>
            </span>
          )}
          <Badge variant="info" size="xs">
            SQL: {sqlCount}
          </Badge>
          <Badge variant="purple" size="xs">
            RAG: {ragCount}
          </Badge>
        </div>
      </div>

      {/* Visual DAG Steps Flow */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2.5 sm:gap-3 relative">
        {/* Step 0: Input Guardrails */}
        <div
          className={`p-3 sm:p-3.5 rounded-xl border transition-all flex flex-col justify-between space-y-2 ${
            status === "guardrail_rejected"
              ? "bg-rose-950/50 border-rose-700 text-rose-200 shadow-sm"
              : "bg-surface-950/90 border-surface-800/90 text-surface-300"
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono text-surface-400 font-semibold uppercase">Step 0</span>
            {status === "guardrail_rejected" ? (
              <ShieldAlert className="w-4 h-4 text-rose-400" />
            ) : (
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
            )}
          </div>
          <div>
            <div className="text-xs font-semibold text-surface-100">Guardrails</div>
            <p className="text-[10px] text-surface-400 mt-0.5">Prompt injection safety</p>
          </div>
          <div className="pt-2 border-t border-surface-800/80 text-[10px] flex items-center justify-between">
            {status === "guardrail_rejected" ? (
              <span className="text-rose-400 font-medium">Rejected</span>
            ) : (
              <span className="text-emerald-400 font-medium flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3" /> Passed
              </span>
            )}
          </div>
        </div>

        {/* Step 1: Planner & Triage */}
        <div
          className={`p-3 sm:p-3.5 rounded-xl border transition-all flex flex-col justify-between space-y-2 ${
            isNodeActive("planner")
              ? "bg-indigo-950/60 border-indigo-500 ring-2 ring-indigo-500/30 text-white animate-pulse"
              : hasExecuted("planner")
              ? "bg-surface-950/90 border-surface-750 text-surface-200"
              : "bg-surface-950/40 border-surface-850 text-surface-400"
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono text-surface-400 font-semibold uppercase">Step 1</span>
            <Brain className="w-4 h-4 text-indigo-400" />
          </div>
          <div>
            <div className="text-xs font-semibold text-surface-100">Planner</div>
            <p className="text-[10px] text-surface-400 mt-0.5">Scope & tool routing</p>
          </div>
          <div className="pt-2 border-t border-surface-800/80 text-[10px] flex items-center justify-between">
            <span className="text-surface-300 font-mono truncate">
              {status === "unsupported"
                ? "Unsupported"
                : status === "needs_clarification"
                ? "Clarify"
                : "Investigating"}
            </span>
          </div>
        </div>

        {/* Step 2: Data Investigator (SQL) */}
        <div
          className={`p-3 sm:p-3.5 rounded-xl border transition-all flex flex-col justify-between space-y-2 ${
            isNodeActive("data_investigator")
              ? "bg-sky-950/60 border-sky-500 ring-2 ring-sky-500/30 text-white animate-pulse"
              : hasExecuted("data_investigator")
              ? "bg-surface-950/90 border-surface-750 text-surface-200"
              : "bg-surface-950/40 border-surface-850 text-surface-400"
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono text-surface-400 font-semibold uppercase">Step 2</span>
            <Database className="w-4 h-4 text-sky-400" />
          </div>
          <div>
            <div className="text-xs font-semibold text-surface-100">Data Agent</div>
            <p className="text-[10px] text-surface-400 mt-0.5">Allowlisted SQL queries</p>
          </div>
          <div className="pt-2 border-t border-surface-800/80 text-[10px] flex items-center justify-between">
            <span className="text-sky-300 font-mono">{sqlCount} SQL Findings</span>
          </div>
        </div>

        {/* Step 3: Knowledge Agent (RAG) */}
        <div
          className={`p-3 sm:p-3.5 rounded-xl border transition-all flex flex-col justify-between space-y-2 ${
            isNodeActive("knowledge")
              ? "bg-purple-950/60 border-purple-500 ring-2 ring-purple-500/30 text-white animate-pulse"
              : hasExecuted("knowledge")
              ? "bg-surface-950/90 border-surface-750 text-surface-200"
              : "bg-surface-950/40 border-surface-850 text-surface-400"
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono text-surface-400 font-semibold uppercase">Step 3</span>
            <FileText className="w-4 h-4 text-purple-400" />
          </div>
          <div>
            <div className="text-xs font-semibold text-surface-100">Knowledge</div>
            <p className="text-[10px] text-surface-400 mt-0.5">Playbook vector RAG</p>
          </div>
          <div className="pt-2 border-t border-surface-800/80 text-[10px] flex items-center justify-between">
            <span className="text-purple-300 font-mono">{ragCount} Chunks</span>
          </div>
        </div>

        {/* Step 4: Synthesizer & Hypothesis */}
        <div
          className={`p-3 sm:p-3.5 rounded-xl border transition-all flex flex-col justify-between space-y-2 ${
            isNodeActive("synthesizer")
              ? "bg-brand-950/60 border-brand-500 ring-2 ring-brand-500/30 text-white animate-pulse"
              : hasExecuted("synthesizer")
              ? "bg-surface-950/90 border-surface-750 text-surface-200"
              : "bg-surface-950/40 border-surface-850 text-surface-400"
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono text-surface-400 font-semibold uppercase">Step 4</span>
            <Sparkles className="w-4 h-4 text-brand-400" />
          </div>
          <div>
            <div className="text-xs font-semibold text-surface-100">Synthesizer</div>
            <p className="text-[10px] text-surface-400 mt-0.5">Hypothesis & driver mix</p>
          </div>
          <div className="pt-2 border-t border-surface-800/80 text-[10px] flex items-center justify-between">
            <span className="text-surface-300 font-mono">
              {investigation.hypothesis?.drivers?.length
                ? `${investigation.hypothesis.drivers.length} Drivers`
                : "Awaiting"}
            </span>
          </div>
        </div>

        {/* Step 5: Critic & Recommender */}
        <div
          className={`p-3 sm:p-3.5 rounded-xl border transition-all flex flex-col justify-between space-y-2 ${
            isNodeActive("critic") || isNodeActive("recommender")
              ? "bg-emerald-950/60 border-emerald-500 ring-2 ring-emerald-500/30 text-white animate-pulse"
              : hasExecuted("recommender") || hasExecuted("critic")
              ? "bg-surface-950/90 border-surface-750 text-surface-200"
              : "bg-surface-950/40 border-surface-850 text-surface-400"
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono text-surface-400 font-semibold uppercase">Step 5</span>
            <Scale className="w-4 h-4 text-amber-400" />
          </div>
          <div>
            <div className="text-xs font-semibold text-surface-100">Critic & Actions</div>
            <p className="text-[10px] text-surface-400 mt-0.5">Verification & Grounding</p>
          </div>
          <div className="pt-2 border-t border-surface-800/80 text-[10px] flex items-center justify-between">
            <span className="text-emerald-400 font-medium truncate">
              {status === "completed"
                ? "Grounded"
                : status === "insufficient_evidence"
                ? "Insufficient"
                : "Active"}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
