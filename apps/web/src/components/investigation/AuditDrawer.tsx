import type { ReactNode } from "react";
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

function AuditStatCard({
  icon,
  label,
  children,
}: {
  icon: ReactNode;
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="app-card p-4 space-y-1.5">
      <div className="flex items-center gap-1.5 text-xs text-surface-400">
        {icon}
        <span>{label}</span>
      </div>
      <div className="text-sm text-surface-100">{children}</div>
    </div>
  );
}

export function AuditDrawer({ isOpen, onClose, audit }: AuditDrawerProps) {
  if (!audit) return null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-accent-950 border border-accent-800 flex items-center justify-center shrink-0">
            <ShieldCheck className="w-4 h-4 text-accent-400" />
          </div>
          <span className="font-app-heading text-base text-white truncate">
            Investigation Audit Record
          </span>
        </div>
      }
      subtitle="Immutable run metadata, tool budget consumption, and guardrail verification."
      maxWidth="2xl"
    >
      <div className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <AuditStatCard icon={<Hash className="w-3.5 h-3.5 shrink-0" />} label="Fingerprint">
            <span className="font-mono text-xs break-all">{audit.question_fingerprint}</span>
          </AuditStatCard>

          <AuditStatCard icon={<Activity className="w-3.5 h-3.5 shrink-0" />} label="Tool Budget Used">
            <span className="font-mono">
              {audit.tool_calls_used} / {audit.max_tool_calls}
            </span>
          </AuditStatCard>

          <AuditStatCard icon={<Layers className="w-3.5 h-3.5 shrink-0" />} label="Citation Verified">
            {audit.citation_verified ? (
              <span className="text-emerald-400 flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 shrink-0" />
                Passed (100%)
              </span>
            ) : (
              <span className="text-amber-400 flex items-center gap-1.5">
                <AlertCircle className="w-4 h-4 shrink-0" />
                Unchecked / Fail
              </span>
            )}
          </AuditStatCard>
        </div>

        <div className="app-card p-4 space-y-2">
          <span className="text-xs font-medium text-surface-400 uppercase tracking-wide">
            Redacted Question (PII Guardrail)
          </span>
          <p className="text-sm text-surface-200 leading-relaxed break-words">{audit.question_redacted}</p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="app-card p-4 space-y-2">
            <span className="text-xs font-medium text-surface-400 uppercase tracking-wide block">
              Node Execution Trace
            </span>
            <div className="flex flex-wrap gap-1.5">
              {audit.node_trace?.map((node, idx) => (
                <Badge key={idx} variant="default" size="xs">
                  {node}
                </Badge>
              ))}
            </div>
          </div>

          <div className="app-card p-4 space-y-1">
            <span className="text-xs font-medium text-surface-400 uppercase tracking-wide block">
              Execution Completed
            </span>
            <div className="text-sm text-surface-200">{formatDate(audit.completed_at)}</div>
            <div className="text-xs text-surface-500">Audit schema version: v{audit.audit_version}</div>
          </div>
        </div>

        <div className="space-y-2 pt-2 border-t border-surface-800/60">
          <span className="text-xs font-medium text-surface-400 uppercase tracking-wide block">
            Raw Audit JSON Payload
          </span>
          <pre className="p-4 rounded-xl bg-surface-950 border border-surface-800 font-mono text-xs text-surface-300 overflow-x-auto max-h-48 leading-relaxed">
            {JSON.stringify(audit, null, 2)}
          </pre>
        </div>
      </div>
    </Modal>
  );
}
