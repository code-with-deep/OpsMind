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
    <div className="bg-surface-900 border border-surface-800 rounded-2xl p-4 sm:p-6 shadow-sm space-y-4 sm:space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between pb-3 border-b border-surface-800 gap-2">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-8 h-8 rounded-lg bg-emerald-950 border border-emerald-800 flex items-center justify-center text-emerald-400 shrink-0">
            <UserCheck className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <h3 className="text-xs sm:text-sm font-semibold text-surface-100 truncate">
              Human-in-the-Loop Review (P6)
            </h3>
            <p className="text-[10px] sm:text-[11px] text-surface-400 truncate">
              Approvals promote findings to Episodic Case Memory
            </p>
          </div>
        </div>

        {caseSummary && (
          <Badge variant="success" size="xs" dot className="shrink-0">
            Case Stored
          </Badge>
        )}
      </div>

      {/* Case Memory Banner if already promoted */}
      {caseSummary && (
        <div className="p-3.5 sm:p-4 rounded-xl bg-emerald-950/30 border border-emerald-800/60 text-xs text-emerald-200 flex items-start gap-2.5 sm:gap-3">
          <Brain className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
          <div className="space-y-1 min-w-0">
            <div className="font-semibold text-emerald-100 truncate">
              Promoted to Case Memory: {caseSummary.title}
            </div>
            <div className="text-[11px] text-emerald-300/80 leading-relaxed font-sans break-words">
              {caseSummary.summary}
            </div>
          </div>
        </div>
      )}

      {/* Review Submission Form */}
      <form onSubmit={handleSubmit} className="space-y-3.5 sm:space-y-4">
        {/* Decision Toggle */}
        <div className="space-y-1.5">
          <label className="text-[10px] sm:text-[11px] font-mono uppercase tracking-wider text-surface-400 font-semibold block">
            Review Decision
          </label>
          <div className="grid grid-cols-3 gap-1.5 sm:gap-2">
            <button
              type="button"
              onClick={() => setDecision("approved")}
              className={`flex items-center justify-center gap-1 sm:gap-1.5 py-2 px-1.5 sm:px-3 rounded-lg border text-[11px] sm:text-xs font-semibold transition-all ${
                decision === "approved"
                  ? "bg-emerald-950/80 border-emerald-500 text-emerald-200 ring-1 ring-emerald-500/30 shadow-sm"
                  : "bg-surface-950 border-surface-800 text-surface-400 hover:text-surface-200"
              }`}
            >
              <CheckCircle className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
              <span className="truncate">Approve</span>
            </button>

            <button
              type="button"
              onClick={() => setDecision("rejected")}
              className={`flex items-center justify-center gap-1 sm:gap-1.5 py-2 px-1.5 sm:px-3 rounded-lg border text-[11px] sm:text-xs font-semibold transition-all ${
                decision === "rejected"
                  ? "bg-rose-950/80 border-rose-500 text-rose-200 ring-1 ring-rose-500/30 shadow-sm"
                  : "bg-surface-950 border-surface-800 text-surface-400 hover:text-surface-200"
              }`}
            >
              <XCircle className="w-3.5 h-3.5 text-rose-400 shrink-0" />
              <span className="truncate">Reject</span>
            </button>

            <button
              type="button"
              onClick={() => setDecision("comment")}
              className={`flex items-center justify-center gap-1 sm:gap-1.5 py-2 px-1.5 sm:px-3 rounded-lg border text-[11px] sm:text-xs font-semibold transition-all ${
                decision === "comment"
                  ? "bg-indigo-950/80 border-indigo-500 text-indigo-200 ring-1 ring-indigo-500/30 shadow-sm"
                  : "bg-surface-950 border-surface-800 text-surface-400 hover:text-surface-200"
              }`}
            >
              <MessageSquare className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
              <span className="truncate">Comment</span>
            </button>
          </div>
        </div>

        {/* Reviewer identity */}
        <div className="space-y-1">
          <label className="text-[10px] sm:text-[11px] font-mono text-surface-400 block font-semibold">
            Reviewer Handle / Email
          </label>
          <input
            type="text"
            required
            value={reviewer}
            onChange={(e) => setReviewer(e.target.value)}
            className="w-full px-3 py-1.5 sm:py-2 bg-surface-950 border border-surface-750 rounded-lg text-xs sm:text-sm text-surface-200 focus:outline-none focus:border-brand-500"
            placeholder="e.g. operator@opsmind.internal"
          />
        </div>

        {/* Operator notes */}
        <div className="space-y-1">
          <label className="text-[10px] sm:text-[11px] font-mono text-surface-400 block font-semibold">
            Operator Feedback / Notes
          </label>
          <textarea
            rows={3}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            className="w-full p-2.5 bg-surface-950 border border-surface-750 rounded-lg text-xs sm:text-sm text-surface-200 placeholder:text-surface-500 focus:outline-none focus:border-brand-500 resize-none"
            placeholder="Add operational context, feedback on suggested actions, or mitigation notes..."
          />
        </div>

        <Button
          type="submit"
          variant={
            decision === "approved"
              ? "success"
              : decision === "rejected"
              ? "danger"
              : "primary"
          }
          size="sm"
          loading={loading}
          className="w-full font-semibold"
        >
          {decision === "approved"
            ? "Approve & Save Case"
            : decision === "rejected"
            ? "Submit Rejection"
            : "Submit Comment"}
        </Button>
      </form>

      {/* Review History */}
      {reviews.length > 0 && (
        <div className="space-y-2 pt-3 border-t border-surface-800">
          <span className="text-[10px] font-mono font-semibold uppercase tracking-wider text-surface-400 block">
            Audit Review Log ({reviews.length})
          </span>
          <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
            {reviews.map((rev) => (
              <div
                key={rev.id}
                className="p-2.5 sm:p-3 rounded-lg bg-surface-950 border border-surface-800 text-xs flex items-start justify-between gap-2"
              >
                <div className="space-y-1 min-w-0 flex-1">
                  <div className="flex items-center gap-1.5 sm:gap-2 flex-wrap">
                    <span className="font-semibold text-surface-200 truncate max-w-[140px] sm:max-w-none">
                      {rev.reviewer}
                    </span>
                    <Badge
                      variant={
                        rev.decision === "approved"
                          ? "success"
                          : rev.decision === "rejected"
                          ? "error"
                          : "purple"
                      }
                      size="xs"
                    >
                      {rev.decision}
                    </Badge>
                  </div>
                  {rev.notes && (
                    <p className="text-[11px] text-surface-300 italic font-sans leading-snug break-words">
                      "{rev.notes}"
                    </p>
                  )}
                </div>
                <span className="text-[10px] text-surface-400 font-mono shrink-0">
                  {formatDate(rev.created_at)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
