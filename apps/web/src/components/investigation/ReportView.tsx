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
import { ProseBlock, SectionCard } from "../common/AppUI";

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

      {(rec?.assumptions?.length || critique?.notes) && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {rec?.assumptions && rec.assumptions.length > 0 && (
            <div className="app-card p-4 space-y-2">
              <div className="flex items-center gap-2 text-amber-400 text-sm font-medium">
                <Info className="w-4 h-4" />
                Assumptions
              </div>
              <ul className="space-y-1.5 text-sm text-surface-300 list-disc list-inside leading-relaxed">
                {rec.assumptions.map((asm, idx) => (
                  <li key={idx}>{asm}</li>
                ))}
              </ul>
            </div>
          )}

          {critique?.notes && (
            <div className="app-card p-4 space-y-2">
              <div className="flex items-center gap-2 text-accent-400 text-sm font-medium">
                <Scale className="w-4 h-4" />
                Critic Notes
              </div>
              <p className="text-sm text-surface-300 leading-relaxed">{critique.notes}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
