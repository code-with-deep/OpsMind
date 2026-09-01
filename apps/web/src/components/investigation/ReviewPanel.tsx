import { useState } from "react";
import {
  Brain,
  CheckCircle,
  MessageSquare,
  UserCheck,
  XCircle,
} from "lucide-react";
import { InvestigationDetail, ReviewDecision } from "../../types";
import { formatDate } from "../../lib/utils";
import { Badge } from "../common/Badge";
import { Button } from "../common/Button";
import { SectionCard } from "../common/AppUI";

interface ReviewPanelProps {
  investigation: InvestigationDetail;
  onSubmitReview: (payload: {
    decision: ReviewDecision;
    reviewer: string;
    notes?: string;
  }) => Promise<void>;
  loading?: boolean;
}

export function ReviewPanel({
  investigation,
  onSubmitReview,
  loading = false,
}: ReviewPanelProps) {
  const [decision, setDecision] = useState<ReviewDecision>("approved");
  const [reviewer, setReviewer] = useState("operator@opsmind.internal");
  const [notes, setNotes] = useState("");
  const reviews = investigation.reviews || [];
  const caseSummary = investigation.case_summary;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmitReview({
      decision,
      reviewer: reviewer.trim(),
      notes: notes.trim() || undefined,
    });
  };

  return (
    <SectionCard
      title="Operator Review"
      subtitle="Approve to save this resolution to Case Memory"
      icon={<UserCheck className="w-4 h-4" />}
      badge={
        caseSummary ? (
          <Badge variant="success" size="xs" dot>
            Saved
          </Badge>
        ) : undefined
      }
      noPadding
    >
      {caseSummary && (
        <div className="px-5 pt-4">
          <div className="p-4 rounded-xl bg-accent-950/30 border border-accent-800/50 text-sm text-accent-100 flex items-start gap-3">
            <Brain className="w-4 h-4 text-accent-400 shrink-0 mt-0.5" />
            <div className="min-w-0 space-y-1">
              <p className="font-medium">{caseSummary.title}</p>
              <p className="text-xs text-accent-200/80 leading-relaxed">{caseSummary.summary}</p>
            </div>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="p-5 space-y-4">
        <div className="space-y-2">
          <label className="text-xs font-medium text-surface-400">Decision</label>
          <div className="grid grid-cols-1 xs:grid-cols-3 gap-2">
            {(
              [
                { key: "approved" as const, label: "Approve", icon: CheckCircle, color: "emerald" },
                { key: "rejected" as const, label: "Reject", icon: XCircle, color: "rose" },
                { key: "comment" as const, label: "Comment", icon: MessageSquare, color: "indigo" },
              ] as const
            ).map(({ key, label, icon: Icon }) => (
              <button
                key={key}
                type="button"
                onClick={() => setDecision(key)}
                className={`flex items-center justify-center gap-1.5 py-2.5 px-2 rounded-lg border text-xs font-medium transition-all ${
                  decision === key
                    ? "bg-accent-950/60 border-accent-500 text-accent-200 ring-1 ring-accent-500/30"
                    : "bg-surface-950/60 border-surface-700 text-surface-400 hover:text-surface-200"
                }`}
              >
                <Icon className="w-3.5 h-3.5 shrink-0" />
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-1.5">
          <label className="text-xs font-medium text-surface-400">Reviewer</label>
          <input
            type="text"
            required
            value={reviewer}
            onChange={(e) => setReviewer(e.target.value)}
            className="app-search-input !pl-3"
            placeholder="your@email.com"
          />
        </div>

        <div className="space-y-1.5">
          <label className="text-xs font-medium text-surface-400">Notes (optional)</label>
          <textarea
            rows={3}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            className="app-search-input !pl-3 resize-none"
            placeholder="Add context or feedback on the recommended actions..."
          />
        </div>

        <Button
          type="submit"
          variant={decision === "approved" ? "accent" : decision === "rejected" ? "danger" : "primary"}
          size="sm"
          loading={loading}
          className="w-full"
        >
          {decision === "approved"
            ? "Approve & Save to Case Memory"
            : decision === "rejected"
            ? "Submit Rejection"
            : "Submit Comment"}
        </Button>
      </form>

      {reviews.length > 0 && (
        <div className="px-5 pb-5 space-y-2 border-t border-surface-800/60 pt-4 mx-0">
          <p className="text-xs font-medium text-surface-400">
            Previous Reviews ({reviews.length})
          </p>
          <div className="space-y-2 max-h-40 overflow-y-auto">
            {reviews.map((rev) => (
              <div key={rev.id} className="p-3 app-card text-xs flex justify-between gap-3">
                <div className="min-w-0 space-y-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-medium text-surface-200">{rev.reviewer}</span>
                    <Badge
                      variant={
                        rev.decision === "approved"
                          ? "success"
                          : rev.decision === "rejected"
                          ? "error"
                          : "default"
                      }
                      size="xs"
                    >
                      {rev.decision}
                    </Badge>
                  </div>
                  {rev.notes && (
                    <p className="text-surface-400 leading-relaxed">"{rev.notes}"</p>
                  )}
                </div>
                <span className="text-[10px] text-surface-500 font-mono shrink-0">
                  {formatDate(rev.created_at)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </SectionCard>
  );
}
