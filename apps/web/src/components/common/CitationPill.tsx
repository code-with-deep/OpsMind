import { cn } from "../../lib/utils";
import { Database, FileText, ExternalLink } from "lucide-react";

interface CitationPillProps {
  sourceId: string;
  onClick?: (sourceId: string) => void;
  className?: string;
}

export function CitationPill({ sourceId, onClick, className }: CitationPillProps) {
  const isSql = sourceId.startsWith("sql_");
  const isRag = sourceId.startsWith("rag_");

  return (
    <button
      type="button"
      onClick={() => onClick?.(sourceId)}
      className={cn(
        "inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-mono transition-all duration-150 border select-none group",
        isSql
          ? "bg-sky-950/50 hover:bg-sky-900/60 text-sky-300 border-sky-800/60 hover:border-sky-700"
          : isRag
          ? "bg-purple-950/50 hover:bg-purple-900/60 text-purple-300 border-purple-800/60 hover:border-purple-700"
          : "bg-surface-800 hover:bg-surface-700 text-surface-300 border-surface-700",
        className
      )}
      title={`Click to inspect evidence source: ${sourceId}`}
    >
      {isSql ? (
        <Database className="w-3 h-3 text-sky-400 shrink-0" />
      ) : isRag ? (
        <FileText className="w-3 h-3 text-purple-400 shrink-0" />
      ) : null}
      <span>{sourceId}</span>
      <ExternalLink className="w-2.5 h-2.5 opacity-0 group-hover:opacity-100 transition-opacity text-current" />
    </button>
  );
}
