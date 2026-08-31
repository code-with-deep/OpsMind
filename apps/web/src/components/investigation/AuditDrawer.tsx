import { Modal } from "../common/Modal";
import { AuditRecord } from "../../types";
import { formatDate } from "../../lib/utils";
import { Badge } from "../common/Badge";
import {
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  Hash,
  Activity,
  Layers,
} from "lucide-react";

interface AuditDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  audit: AuditRecord | null;
}

export function AuditDrawer({ isOpen, onClose, audit }: AuditDrawerProps) {
  if (!audit) return null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-5 h-5 text-brand-400 shrink-0" />
          <span className="truncate">Investigation Audit Record</span>
        </div>
      }
      subtitle="Immutable run metadata, tool budget consumption, and guardrail verification."
      maxWidth="2xl"
    >
      <div className="space-y-4 text-xs font-sans">
        {/* Top Cards: Fingerprint, Budget, Citation Verified */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 sm:gap-3">
          <div className="p-3 bg-surface-950 border border-surface-800 rounded-xl">
            <div className="flex items-center gap-1.5 text-surface-400 mb-1">
              <Hash className="w-3.5 h-3.5 shrink-0" />
              <span>Fingerprint</span>
            </div>
            <div className="font-mono font-bold text-surface-100 text-xs sm:text-sm break-all">
              {audit.question_fingerprint}
            </div>
          </div>

          <div className="p-3 bg-surface-950 border border-surface-800 rounded-xl">
            <div className="flex items-center gap-1.5 text-surface-400 mb-1">
              <Activity className="w-3.5 h-3.5 shrink-0" />
              <span>Tool Budget Used</span>
            </div>
            <div className="font-mono font-bold text-surface-100 text-xs sm:text-sm">
              {audit.tool_calls_used} / {audit.max_tool_calls}
            </div>
          </div>

          <div className="p-3 bg-surface-950 border border-surface-800 rounded-xl">
            <div className="flex items-center gap-1.5 text-surface-400 mb-1">
              <Layers className="w-3.5 h-3.5 shrink-0" />
              <span>Citation Verified</span>
            </div>
            <div className="font-semibold text-xs sm:text-sm">
              {audit.citation_verified ? (
                <span className="text-emerald-400 flex items-center gap-1">
                  <CheckCircle2 className="w-4 h-4" /> Passed (100%)
                </span>
              ) : (
                <span className="text-amber-400 flex items-center gap-1">
                  <AlertCircle className="w-4 h-4" /> Unchecked / Fail
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Redacted Question */}
        <div className="p-3.5 bg-surface-950 border border-surface-800 rounded-xl space-y-1">
          <span className="text-[10px] sm:text-[11px] font-semibold text-surface-400 uppercase tracking-wider block">
            Redacted Question (PII Guardrail)
          </span>
          <p className="font-mono text-surface-200 text-xs leading-relaxed break-words">
            {audit.question_redacted}
          </p>
        </div>

        {/* Node Trace & Completed At */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 sm:gap-3">
          <div className="p-3.5 bg-surface-950 border border-surface-800 rounded-xl space-y-1.5">
            <span className="text-[10px] sm:text-[11px] font-semibold text-surface-400 uppercase tracking-wider block">
              Node Execution Trace
            </span>
            <div className="flex flex-wrap gap-1">
              {audit.node_trace?.map((node, idx) => (
                <Badge key={idx} variant="default" size="xs">
                  {node}
                </Badge>
              ))}
            </div>
          </div>

          <div className="p-3.5 bg-surface-950 border border-surface-800 rounded-xl space-y-1">
            <span className="text-[10px] sm:text-[11px] font-semibold text-surface-400 uppercase tracking-wider block">
              Execution Completed
            </span>
            <div className="text-surface-200 font-mono text-xs">
              {formatDate(audit.completed_at)}
            </div>
            <div className="text-surface-500 text-[10px] sm:text-[11px]">
              Audit schema version: v{audit.audit_version}
            </div>
          </div>
        </div>

        {/* Raw JSON viewer */}
        <div className="space-y-1.5 pt-2 border-t border-surface-800">
          <span className="text-[10px] sm:text-[11px] font-semibold text-surface-400 uppercase tracking-wider block">
            Raw Audit JSON Payload
          </span>
          <pre className="p-3 bg-surface-950 border border-surface-800 rounded-xl font-mono text-[10px] sm:text-[11px] text-surface-300 overflow-x-auto max-h-48 leading-relaxed">
            {JSON.stringify(audit, null, 2)}
          </pre>
        </div>
      </div>
    </Modal>
  );
}
