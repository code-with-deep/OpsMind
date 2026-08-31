import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "N/A";
  try {
    const d = new Date(dateStr);
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(d);
  } catch {
    return dateStr;
  }
}

export function formatConfidence(val: number | null | undefined): string {
  if (val === null || val === undefined) return "--";
  return `${Math.round(val * 100)}%`;
}

export function getConfidenceTone(val: number | null | undefined): {
  color: string;
  bg: string;
  border: string;
  label: string;
} {
  if (val === null || val === undefined) {
    return {
      color: "text-surface-400",
      bg: "bg-surface-800",
      border: "border-surface-700",
      label: "Unscored",
    };
  }
  if (val >= 0.8) {
    return {
      color: "text-emerald-400",
      bg: "bg-emerald-950/40",
      border: "border-emerald-800/50",
      label: "High Confidence",
    };
  }
  if (val >= 0.5) {
    return {
      color: "text-amber-400",
      bg: "bg-amber-950/40",
      border: "border-amber-800/50",
      label: "Moderate Confidence",
    };
  }
  return {
    color: "text-rose-400",
    bg: "bg-rose-950/40",
    border: "border-rose-800/50",
    label: "Low / Abstain",
  };
}

export function getStatusBadgeConfig(status: string): {
  label: string;
  className: string;
  dotColor: string;
} {
  switch (status) {
    case "completed":
      return {
        label: "Completed",
        className: "bg-emerald-950/50 text-emerald-300 border-emerald-800/60",
        dotColor: "bg-emerald-400",
      };
    case "running":
      return {
        label: "Investigating",
        className: "bg-indigo-950/50 text-indigo-300 border-indigo-800/60 animate-pulse",
        dotColor: "bg-indigo-400",
      };
    case "unsupported":
      return {
        label: "Unsupported Domain",
        className: "bg-slate-900 text-slate-300 border-slate-700",
        dotColor: "bg-slate-400",
      };
    case "needs_clarification":
      return {
        label: "Needs Clarification",
        className: "bg-amber-950/50 text-amber-300 border-amber-800/60",
        dotColor: "bg-amber-400",
      };
    case "insufficient_evidence":
      return {
        label: "Insufficient Evidence",
        className: "bg-orange-950/50 text-orange-300 border-orange-800/60",
        dotColor: "bg-orange-400",
      };
    case "budget_exceeded":
      return {
        label: "Budget Exceeded",
        className: "bg-red-950/50 text-red-300 border-red-800/60",
        dotColor: "bg-red-400",
      };
    case "guardrail_rejected":
      return {
        label: "Guardrail Rejected",
        className: "bg-rose-950/50 text-rose-300 border-rose-800/60",
        dotColor: "bg-rose-400",
      };
    case "failed":
      return {
        label: "System Failed",
        className: "bg-rose-950/50 text-rose-300 border-rose-800/60",
        dotColor: "bg-rose-400",
      };
    default:
      return {
        label: status || "Open",
        className: "bg-surface-800 text-surface-300 border-surface-700",
        dotColor: "bg-surface-400",
      };
  }
}
