import { cn, formatConfidence, getConfidenceTone } from "../../lib/utils";
import { ShieldCheck } from "lucide-react";

interface ConfidenceMeterProps {
  value: number | null | undefined;
  size?: "sm" | "md" | "lg";
  showLabel?: boolean;
  className?: string;
}

export function ConfidenceMeter({
  value,
  size = "md",
  showLabel = true,
  className,
}: ConfidenceMeterProps) {
  const tone = getConfidenceTone(value);
  const percentage = value !== null && value !== undefined ? Math.round(value * 100) : 0;

  if (size === "sm") {
    return (
      <div className={cn("inline-flex items-center gap-1.5", className)}>
        <div className="w-12 h-1.5 bg-surface-800 rounded-full overflow-hidden border border-surface-700/50">
          <div
            className={cn(
              "h-full rounded-full transition-all duration-500",
              percentage >= 80
                ? "bg-emerald-500"
                : percentage >= 50
                ? "bg-amber-500"
                : "bg-rose-500"
            )}
            style={{ width: `${percentage}%` }}
          />
        </div>
        <span className={cn("text-xs font-mono font-medium", tone.color)}>
          {formatConfidence(value)}
        </span>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "flex items-center gap-3 px-3 py-2 rounded-lg border",
        tone.bg,
        tone.border,
        className
      )}
    >
      <div className="shrink-0">
        <ShieldCheck className={cn("w-5 h-5", tone.color)} />
      </div>
      <div className="flex-1 min-w-0">
        {showLabel && (
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="text-surface-300 font-medium">{tone.label}</span>
            <span className={cn("font-mono font-semibold", tone.color)}>
              {formatConfidence(value)}
            </span>
          </div>
        )}
        <div className="w-full h-2 bg-surface-900/80 rounded-full overflow-hidden border border-surface-700/60">
          <div
            className={cn(
              "h-full rounded-full transition-all duration-700",
              percentage >= 80
                ? "bg-gradient-to-r from-emerald-600 to-emerald-400"
                : percentage >= 50
                ? "bg-gradient-to-r from-amber-600 to-amber-400"
                : "bg-gradient-to-r from-rose-600 to-rose-400"
            )}
            style={{ width: `${percentage}%` }}
          />
        </div>
      </div>
    </div>
  );
}
