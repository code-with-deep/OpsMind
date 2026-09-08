import { useState } from "react";
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  Copy,
  ExternalLink,
  Layers,
  ListOrdered,
  Scale,
  Sparkles,
  TrendingDown,
  XCircle,
} from "lucide-react";
import { InvestigationDetail } from "../../types";
import { Badge } from "../common/Badge";
import { Button } from "../common/Button";
import { CitationPill } from "../common/CitationPill";
import { ConfidenceMeter } from "../common/ConfidenceMeter";
import { ProseBlock, SectionCard } from "../common/AppUI";

// ── Critic Verdict Card ────────────────────────────────────────────────────

interface CriticVerdictCardProps {
  critique: InvestigationDetail["critique"];
}

const VERDICT_CONFIG = {
  pass: {
    icon: <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />,
    label: "Passed",
    labelClass: "text-emerald-400",
    borderClass: "border-emerald-800/50",
    bgClass: "bg-emerald-950/25",
    headline: "All claims are fully verified.",
    body: "Every number and recommendation in this report is directly backed by SQL query results or SOP playbook evidence. You can act on this with confidence.",
  },
  fail_soft: {
    icon: <AlertTriangle className="w-4 h-4 shrink-0 text-amber-400" />,
    label: "Soft Fail",
    labelClass: "text-amber-400",
    borderClass: "border-amber-800/50",
    bgClass: "bg-amber-950/20",
    headline: "Some claims could not be fully verified.",
    body: "The Critic checked the report twice and found that not all numbers or recommendations could be traced back to SQL data or playbooks. The report shows the best available answer — review it carefully before acting.",
  },
  retry: {
    icon: <AlertTriangle className="w-4 h-4 shrink-0 text-amber-400" />,
    label: "Retried",
    labelClass: "text-amber-400",
    borderClass: "border-amber-800/50",
    bgClass: "bg-amber-950/20",
    headline: "The Critic flagged issues and the pipeline retried.",
    body: "One or more verification checks failed. The pipeline automatically retried and produced an improved answer. Review the findings below before acting.",
  },
} as const;

function CriticVerdictCard({ critique }: CriticVerdictCardProps) {
  if (!critique) {
    // Pipeline didn't reach the Critic (e.g. unsupported question / guardrail rejection)
    return (
      <div className="app-card p-4 flex items-start gap-3 border border-surface-700/60">
        <XCircle className="w-4 h-4 shrink-0 text-surface-500 mt-0.5" />
        <div className="min-w-0 space-y-1">
          <div className="flex items-center gap-2">
            <Scale className="w-3.5 h-3.5 text-surface-500" />
            <span className="text-sm font-medium text-surface-400">Critic — Not evaluated</span>
          </div>
          <p className="text-sm text-surface-500 leading-relaxed">
            The investigation did not reach the verification stage. This usually means the question
            was outside the supported domain or was blocked by the input guardrail.
          </p>
        </div>
      </div>
    );
  }

  const cfg = VERDICT_CONFIG[critique.decision] ?? VERDICT_CONFIG.pass;
  const hasGaps = critique.gaps && critique.gaps.length > 0;

  return (
    <div className={`app-card p-4 space-y-3 border ${cfg.borderClass} ${cfg.bgClass}`}>
      {/* Header row */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Scale className="w-4 h-4 text-surface-400" />
          <span className="text-sm font-medium text-surface-300">Critic Verdict</span>
        </div>
        <div className={`flex items-center gap-1.5 text-xs font-semibold ${cfg.labelClass}`}>
          {cfg.icon}
          {cfg.label}
        </div>
      </div>

      {/* Verdict explanation */}
      <div className="space-y-1">
        <p className="text-sm font-medium text-surface-100">{cfg.headline}</p>
        <p className="text-sm text-surface-400 leading-relaxed">{cfg.body}</p>
      </div>

      {/* Critic notes (if any) */}
      {critique.notes && (
        <p className="text-xs text-surface-400 italic border-l-2 border-surface-700 pl-3 leading-relaxed">
          {critique.notes}
        </p>
      )}

      {/* What the Critic flagged (gaps) */}
      {hasGaps && (
        <div className="space-y-1.5 pt-1 border-t border-surface-800/60">
          <p className="text-xs font-medium text-surface-400 uppercase tracking-wide">
            What the Critic flagged
          </p>
          <ul className="space-y-1">
            {critique.gaps.map((gap, idx) => (
              <li key={idx} className="flex items-start gap-2 text-xs text-surface-400 leading-relaxed">
                <span className="shrink-0 text-amber-500 mt-0.5">•</span>
                <span>{gap}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

interface ReportViewProps {
  investigation: InvestigationDetail;
  onSelectSource?: (sourceId: string) => void;
  onAuditClick?: () => void;
}

export function ReportView({
  investigation,
  onSelectSource,
  onAuditClick,
}: ReportViewProps) {
  const [copied, setCopied] = useState(false);
  const rec = investigation.recommendation;
  const hyp = investigation.hypothesis;
  const critique = investigation.critique;

  const handleCopyMarkdown = () => {
    const lines = [
      `# Investigation Report: ${investigation.question}`,
      `**Status:** ${investigation.status.toUpperCase()} | **Confidence:** ${Math.round((investigation.confidence || 0) * 100)}%`,
      `**Run ID:** ${investigation.id}`,
      "",
      "## Executive Summary",
      rec?.summary || hyp?.summary || "No summary available.",
      "",
      "## Identified Operational Drivers",
      ...(hyp?.drivers?.map((d) => `- ${d}`) || ["- None identified"]),
      "",
      "## Recommended Actions",
      ...(rec?.actions?.map((a) => `- ${a}`) || ["- None available"]),
      "",
      "## Citations & Grounding",
      ...(rec?.claim_source_map?.map((cs) => `- **${cs.claim}**: [${cs.source_ids.join(", ")}]`) || []),
    ];

    navigator.clipboard.writeText(lines.join("\n"));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-5">
      <SectionCard
        title="Executive Summary"
        subtitle="Root-cause analysis from SQL data and SOP playbooks"
        icon={<Sparkles className="w-4 h-4" />}
        action={
          <div className="flex items-center gap-2 flex-wrap justify-end w-full sm:w-auto">
            {investigation.audit && (
              <button
                type="button"
                onClick={onAuditClick}
                className="text-xs text-accent-400 hover:text-accent-300 font-mono flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-surface-700 hover:border-accent-600 transition-colors"
              >
                Audit
                <ExternalLink className="w-3 h-3" />
              </button>
            )}
            <Button
              variant="outline"
              size="xs"
              icon={copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
              onClick={handleCopyMarkdown}
            >
              {copied ? "Copied" : "Copy"}
            </Button>
          </div>
        }
      >
        <ProseBlock>
          {rec?.summary || hyp?.summary || (
            <span className="text-surface-400 italic">
              Investigation in progress. Summary will appear once agents finish gathering evidence.
            </span>
          )}
        </ProseBlock>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-5">
          <ConfidenceMeter value={investigation.confidence} className="sm:col-span-2" />
          <div className="flex items-center justify-between px-4 py-3 app-card text-sm">
            <div className="flex items-center gap-2 text-surface-300">
              <Scale className="w-4 h-4 text-amber-400" />
              <span>Critic</span>
            </div>
            <span className="font-mono font-semibold text-white">
              {critique?.decision ? critique.decision.toUpperCase() : "PASS"}
            </span>
          </div>
        </div>

        {hyp?.drivers && hyp.drivers.length > 0 && (
          <div className="mt-5 pt-5 border-t border-surface-800/60">
            <p className="text-xs font-medium text-surface-400 uppercase tracking-wider mb-2">
              Root-Cause Drivers
            </p>
            <div className="flex flex-wrap gap-2">
              {hyp.drivers.map((driver, idx) => (
                <Badge key={idx} variant="success" size="md">
                  <TrendingDown className="w-3.5 h-3.5 shrink-0" />
                  <span>{driver}</span>
                </Badge>
              ))}
            </div>
          </div>
        )}
      </SectionCard>

      {rec?.actions && rec.actions.length > 0 && (
        <SectionCard
          title="Recommended Actions"
          subtitle="Each action is backed by verified SQL or playbook citations"
          icon={<ListOrdered className="w-4 h-4" />}
          badge={
            <Badge variant="success" size="xs" dot>
              Verified
            </Badge>
          }
        >
          <div className="space-y-3">
            {rec.actions.map((action, idx) => {
              const claimMatch = rec.claim_source_map?.find(
                (cm) =>
                  cm.claim.toLowerCase().includes(action.toLowerCase()) ||
                  action.toLowerCase().includes(cm.claim.toLowerCase())
              );
              const sourceIds = claimMatch?.source_ids || [];

              return (
                <div key={idx} className="app-action-item">
                  <span className="app-action-number">{idx + 1}</span>
                  <div className="flex-1 min-w-0 space-y-2">
                    <p className="text-sm text-surface-100 leading-relaxed">{action}</p>
                    {sourceIds.length > 0 && (
                      <div className="flex items-center gap-1.5 flex-wrap">
                        {sourceIds.map((sid) => (
                          <CitationPill key={sid} sourceId={sid} onClick={onSelectSource} />
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </SectionCard>
      )}

      {rec?.claim_source_map && rec.claim_source_map.length > 0 && (
        <SectionCard
          title="Citation Map"
          subtitle={`${rec.claim_source_map.length} claims linked to evidence sources`}
          icon={<Layers className="w-4 h-4" />}
        >
          <div className="space-y-3">
            {rec.claim_source_map.map((item, idx) => (
              <div
                key={idx}
                className="p-4 app-card space-y-2"
              >
                <p className="text-sm text-surface-100 leading-relaxed">{item.claim}</p>
                <div className="flex items-center gap-1.5 flex-wrap">
                  {item.source_ids.map((sid) => (
                    <CitationPill key={sid} sourceId={sid} onClick={onSelectSource} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      <CriticVerdictCard critique={critique} />
    </div>
  );
}
