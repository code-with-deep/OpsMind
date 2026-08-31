import { useState } from "react";
import {
  Check,
  Copy,
  ExternalLink,
  Info,
  Layers,
  ListOrdered,
  Scale,
  Sparkles,
  TrendingDown,
} from "lucide-react";
import { InvestigationDetail } from "../../types";
import { Badge } from "../common/Badge";
import { Button } from "../common/Button";
import { CitationPill } from "../common/CitationPill";
import { ConfidenceMeter } from "../common/ConfidenceMeter";

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
    <div className="space-y-4 sm:space-y-6">
      {/* 1. Executive Summary Card */}
      <div className="bg-surface-900 border border-surface-800 rounded-2xl p-4 sm:p-6 shadow-sm space-y-4 sm:space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-surface-800">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-brand-950 border border-brand-800 flex items-center justify-center text-brand-400 shrink-0">
              <Sparkles className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <h2 className="text-xs sm:text-base font-semibold text-surface-100 truncate">
                Synthesis & Executive Summary
              </h2>
              <p className="text-[10px] sm:text-[11px] text-surface-400 truncate">
                Grounded multi-driver analysis formulated by Synthesizer agent
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            {investigation.audit && (
              <button
                type="button"
                onClick={onAuditClick}
                className="text-[11px] sm:text-xs text-brand-400 hover:text-brand-300 font-mono flex items-center gap-1.5 bg-surface-950 px-2.5 py-1 rounded-lg border border-surface-750 hover:border-brand-500 transition-colors shadow-sm"
                title="View cryptographic audit log (SHA-256 fingerprint & token budget)"
              >
                <span>Audit: {investigation.audit.question_fingerprint}</span>
                <ExternalLink className="w-3 h-3" />
              </button>
            )}

            <Button
              variant="outline"
              size="xs"
              icon={copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
              onClick={handleCopyMarkdown}
            >
              {copied ? "Copied" : "Copy Report"}
            </Button>
          </div>
        </div>

        {/* Primary Summary Callout Box */}
        <div className="p-3.5 sm:p-5 rounded-xl bg-surface-950 border border-surface-800 text-xs sm:text-sm text-surface-200 leading-relaxed space-y-2">
          <p className="font-sans break-words">
            {rec?.summary || hyp?.summary || (
              <span className="text-surface-400 italic">
                Investigation in progress. Synthesis will be generated once Data Investigator and Knowledge Agent runs conclude.
              </span>
            )}
          </p>
        </div>

        {/* Confidence Meter & Critic Decision Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 sm:gap-3">
          <ConfidenceMeter value={investigation.confidence} className="sm:col-span-2" />
          <div className="flex items-center justify-between px-3.5 py-2.5 bg-surface-950 rounded-xl border border-surface-800 text-xs">
            <div className="flex items-center gap-2">
              <Scale className="w-4 h-4 text-amber-400 shrink-0" />
              <span className="text-surface-300 font-medium text-xs">Critic Eval</span>
            </div>
            <span className="font-mono font-bold text-surface-100">
              {critique?.decision ? critique.decision.toUpperCase() : "PASS"}
            </span>
          </div>
        </div>

        {/* Identified Driver Tags */}
        {hyp?.drivers && hyp.drivers.length > 0 && (
          <div className="space-y-2">
            <span className="text-[10px] sm:text-[11px] font-mono uppercase tracking-wider text-surface-400 block font-semibold">
              Identified Root-Cause Drivers
            </span>
            <div className="flex flex-wrap gap-1.5 sm:gap-2">
              {hyp.drivers.map((driver, idx) => (
                <Badge key={idx} variant="purple" size="md" className="max-w-full">
                  <TrendingDown className="w-3.5 h-3.5 text-purple-400 shrink-0" />
                  <span className="truncate">{driver}</span>
                </Badge>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 2. Actionable Operations Plan Checklist */}
      {rec?.actions && rec.actions.length > 0 && (
        <div className="bg-surface-900 border border-surface-800 rounded-2xl p-4 sm:p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-surface-800 gap-2">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-8 h-8 rounded-lg bg-emerald-950 border border-emerald-800 flex items-center justify-center text-emerald-400 shrink-0">
                <ListOrdered className="w-4 h-4" />
              </div>
              <div className="min-w-0">
                <h3 className="text-xs sm:text-base font-semibold text-surface-100 truncate">
                  Actionable Operations Plan
                </h3>
                <p className="text-[10px] sm:text-[11px] text-surface-400 truncate">
                  Evidence-backed mitigation actions cited against SQL & playbook sources
                </p>
              </div>
            </div>
            <Badge variant="success" size="xs" dot className="shrink-0">
              Verified
            </Badge>
          </div>

          <div className="space-y-2.5 sm:space-y-3">
            {rec.actions.map((action, idx) => {
              const claimMatch = rec.claim_source_map?.find(
                (cm) =>
                  cm.claim.toLowerCase().includes(action.toLowerCase()) ||
                  action.toLowerCase().includes(cm.claim.toLowerCase())
              );
              const sourceIds = claimMatch?.source_ids || [];

              return (
                <div
                  key={idx}
                  className="p-3.5 sm:p-4 rounded-xl bg-surface-950 border border-surface-800/90 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:border-surface-700 transition-colors"
                >
                  <div className="flex items-start gap-2.5 sm:gap-3 flex-1 min-w-0">
                    <div className="w-5 h-5 rounded-full bg-surface-850 border border-surface-700 text-surface-300 font-mono text-[10px] sm:text-[11px] flex items-center justify-center shrink-0 mt-0.5">
                      {idx + 1}
                    </div>
                    <p className="text-xs sm:text-sm text-surface-200 leading-relaxed font-medium break-words">
                      {action}
                    </p>
                  </div>

                  {sourceIds.length > 0 && (
                    <div className="flex items-center gap-1.5 flex-wrap sm:shrink-0 sm:pl-3 sm:border-l sm:border-surface-800 pt-1 sm:pt-0">
                      <span className="text-[10px] text-surface-400 font-mono">Sources:</span>
                      {sourceIds.map((sid) => (
                        <CitationPill
                          key={sid}
                          sourceId={sid}
                          onClick={onSelectSource}
                        />
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 3. Evidence Citation Mapping Table */}
      {rec?.claim_source_map && rec.claim_source_map.length > 0 && (
        <div className="bg-surface-900 border border-surface-800 rounded-2xl p-4 sm:p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-surface-800 gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <Layers className="w-4 h-4 text-sky-400 shrink-0" />
              <h3 className="text-xs sm:text-sm font-semibold text-surface-100 truncate">
                Evidence Claim $\rightarrow$ Source Verification Matrix
              </h3>
            </div>
            <span className="text-[10px] sm:text-[11px] font-mono text-surface-400 shrink-0">
              {rec.claim_source_map.length} Claims
            </span>
          </div>

          <div className="overflow-x-auto -mx-4 sm:mx-0 px-4 sm:px-0">
            <table className="w-full text-left text-xs border-collapse min-w-[300px]">
              <thead>
                <tr className="border-b border-surface-800 text-[10px] sm:text-[11px] uppercase tracking-wider text-surface-400 font-mono">
                  <th className="py-2.5 px-3">Synthesized Claim</th>
                  <th className="py-2.5 px-3">Verified Source IDs</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-800/60">
                {rec.claim_source_map.map((item, idx) => (
                  <tr key={idx} className="hover:bg-surface-950/50 transition-colors">
                    <td className="py-3 px-3 text-surface-200 font-medium max-w-md break-words">
                      {item.claim}
                    </td>
                    <td className="py-3 px-3">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        {item.source_ids.map((sid) => (
                          <CitationPill
                            key={sid}
                            sourceId={sid}
                            onClick={onSelectSource}
                          />
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 4. Assumptions & Critic Feedback Callout */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 sm:gap-4">
        {rec?.assumptions && rec.assumptions.length > 0 && (
          <div className="p-4 rounded-xl bg-surface-900 border border-surface-800 space-y-2 text-xs">
            <div className="flex items-center gap-2 text-amber-400 font-semibold">
              <Info className="w-4 h-4 shrink-0" />
              <span>Stated Assumptions</span>
            </div>
            <ul className="space-y-1 text-surface-300 text-[11px] list-disc list-inside leading-relaxed">
              {rec.assumptions.map((asm, idx) => (
                <li key={idx} className="break-words">{asm}</li>
              ))}
            </ul>
          </div>
        )}

        {critique?.notes && (
          <div className="p-4 rounded-xl bg-surface-900 border border-surface-800 space-y-2 text-xs">
            <div className="flex items-center gap-2 text-indigo-400 font-semibold">
              <Scale className="w-4 h-4 shrink-0" />
              <span>Critic Self-Correction Notes</span>
            </div>
            <p className="text-surface-300 text-[11px] leading-relaxed break-words">
              {critique.notes}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
