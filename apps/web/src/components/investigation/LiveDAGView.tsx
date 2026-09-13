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
import { SectionCard } from "../common/AppUI";

/** agent_<node>, agent_<node>_done, agent_<node>_degraded (written by each agent). */
const AGENT_EVENT = /^agent_(.+?)(_done|_degraded)?$/;
/** Run concurrently after case memory; each logs a *_done event when finished. */
const PARALLEL_NODES = ["data_investigator", "knowledge"];

interface LiveDAGViewProps {
  investigation: InvestigationDetail;
}

export function LiveDAGView({ investigation }: LiveDAGViewProps) {
  const status = investigation.status;
  const isRunning = status === "running";
  const retryCount = Math.max(investigation.retry_count || 0, investigation.audit?.retry_count || 0);

  // Progress comes from the live timeline, so the pipeline advances while the run
  // is in flight and renders correctly for runs opened later from History.
  const started = new Set<string>([
    ...(investigation.run?.node_trace || []),
    ...(investigation.audit?.node_trace || []),
  ]);
  const finished = new Set<string>();
  let lastNode: string | null = null;
  for (const event of investigation.timeline || []) {
    const match = AGENT_EVENT.exec(event.event_type);
    if (!match) continue;
    started.add(match[1]);
    if (match[2] === "_done") finished.add(match[1]);
    lastNode = match[1];
  }
  const sqlCount = investigation.findings?.filter((f) => f.source_id.startsWith("sql_")).length || 0;
  const ragCount = investigation.findings?.filter((f) => f.source_id.startsWith("rag_")).length || 0;

  const isNodeActive = (nodeKey: string) => {
    if (!isRunning || !started.has(nodeKey)) return false;
    if (PARALLEL_NODES.includes(nodeKey)) return !finished.has(nodeKey);
    return lastNode === nodeKey;
  };

  const hasExecuted = (nodeKey: string) => {
    if (isNodeActive(nodeKey)) return false;
    return started.has(nodeKey) || status === "completed";
  };

  const steps = [
    {
      key: "guardrails",
      step: "0",
      title: "Guardrails",
      sub: "Input safety",
      icon: status === "guardrail_rejected" ? ShieldAlert : ShieldCheck,
      active: false,
      done: status !== "guardrail_rejected",
      status: status === "guardrail_rejected" ? "Rejected" : "Passed",
      statusColor: status === "guardrail_rejected" ? "text-rose-400" : "text-accent-400",
      error: status === "guardrail_rejected",
    },
    {
      key: "planner",
      step: "1",
      title: "Planner",
      sub: "Triage & routing",
      icon: Brain,
      active: isNodeActive("planner"),
      done: hasExecuted("planner"),
      status:
        status === "unsupported"
          ? "Unsupported"
          : status === "needs_clarification"
          ? "Clarify"
          : isNodeActive("planner")
          ? "Planning…"
          : started.has("planner")
          ? "Routed"
          : "Pending",
    },
    {
      key: "data_investigator",
      step: "2",
      title: "Data Agent",
      sub: "SQL queries",
      icon: Database,
      active: isNodeActive("data_investigator"),
      done: hasExecuted("data_investigator"),
      status: `${sqlCount} findings`,
      statusColor: "text-sky-300",
    },
    {
      key: "knowledge",
      step: "3",
      title: "Knowledge",
      sub: "SOP retrieval",
      icon: FileText,
      active: isNodeActive("knowledge"),
      done: hasExecuted("knowledge"),
      status: `${ragCount} chunks`,
      statusColor: "text-purple-300",
    },
    {
      key: "synthesizer",
      step: "4",
      title: "Synthesizer",
      sub: "Hypothesis",
      icon: Sparkles,
      active: isNodeActive("synthesizer"),
      done: hasExecuted("synthesizer"),
      status: investigation.hypothesis?.drivers?.length
        ? `${investigation.hypothesis.drivers.length} drivers`
        : "Pending",
    },
    {
      key: "critic",
      step: "5",
      title: "Critic",
      sub: "Verification",
      icon: Scale,
      active: isNodeActive("critic") || isNodeActive("recommender"),
      done: hasExecuted("recommender") || hasExecuted("critic"),
      status:
        status === "completed"
          ? "Grounded"
          : status === "insufficient_evidence"
          ? "Not grounded"
          : isRunning
          ? started.has("critic")
            ? "Verifying…"
            : "Pending"
          : "—",
      statusColor: status === "completed" ? "text-accent-400" : undefined,
    },
  ];

  return (
    <SectionCard
      title="Agent Pipeline"
      subtitle={isRunning ? "Updating live as each agent runs" : "6-agent LangGraph execution flow"}
      icon={<Zap className="w-4 h-4" />}
      badge={
        <div className="flex flex-wrap items-center gap-1.5">
          {retryCount > 0 && (
            <span className="app-stat-chip text-amber-300">
              <RotateCw className="w-3 h-3" />
              {retryCount} retries
            </span>
          )}
          <Badge variant="info" size="xs">SQL {sqlCount}</Badge>
          <Badge variant="success" size="xs">RAG {ragCount}</Badge>
        </div>
      }
    >
      <div className="flex gap-2.5 overflow-x-auto pb-1 -mx-1 px-1 snap-x snap-mandatory sm:grid sm:grid-cols-3 lg:grid-cols-6 sm:overflow-visible sm:pb-0 sm:mx-0 sm:px-0 sm:snap-none">
        {steps.map((s) => {
          const Icon = s.icon;
          return (
            <div
              key={s.key}
              className={`min-w-[9.5rem] sm:min-w-0 snap-start shrink-0 sm:shrink p-3 rounded-xl border flex flex-col gap-2 transition-all ${
                s.error
                  ? "bg-rose-950/40 border-rose-800/60"
                  : s.active
                  ? "bg-accent-950/40 border-accent-500/50 ring-1 ring-accent-500/20 animate-pulse"
                  : s.done
                  ? "app-card"
                  : "bg-surface-950/30 border-surface-800/40 opacity-60"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono text-surface-500">{s.step}</span>
                <Icon className={`w-4 h-4 ${s.error ? "text-rose-400" : "text-accent-400"}`} />
              </div>
              <div>
                <p className="text-xs font-semibold text-white">{s.title}</p>
                <p className="text-xs text-surface-500">{s.sub}</p>
              </div>
              <p className={`text-xs font-medium ${s.statusColor || "text-surface-400"}`}>
                {s.status}
              </p>
              {s.done && !s.error && (
                <CheckCircle2 className="w-3 h-3 text-accent-500" />
              )}
            </div>
          );
        })}
      </div>
    </SectionCard>
  );
}
