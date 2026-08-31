import { useState } from "react";
import {
  Check,
  ChevronDown,
  ChevronRight,
  Copy,
  Database,
  FileText,
  Layers,
  Search,
} from "lucide-react";
import { Finding } from "../../types";
import { Badge } from "../common/Badge";

interface EvidenceExplorerProps {
  findings: Finding[];
  selectedSourceId?: string | null;
  onSelectSource?: (sourceId: string) => void;
}

export function EvidenceExplorer({
  findings,
  selectedSourceId,
  onSelectSource,
}: EvidenceExplorerProps) {
  const [filterType, setFilterType] = useState<"all" | "sql" | "rag">("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedSourceId, setExpandedSourceId] = useState<string | null>(selectedSourceId || null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const filteredFindings = findings.filter((f) => {
    const isSql = f.source_id.startsWith("sql_");
    const isRag = f.source_id.startsWith("rag_");
    if (filterType === "sql" && !isSql) return false;
    if (filterType === "rag" && !isRag) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      return (
        f.claim.toLowerCase().includes(q) ||
        f.source_id.toLowerCase().includes(q) ||
        f.sources.some(
          (s) =>
            s.title?.toLowerCase().includes(q) ||
            s.template_key?.toLowerCase().includes(q) ||
            s.excerpt?.toLowerCase().includes(q)
        )
      );
    }
    return true;
  });

  const sqlCount = findings.filter((f) => f.source_id.startsWith("sql_")).length;
  const ragCount = findings.filter((f) => f.source_id.startsWith("rag_")).length;

  const handleCopy = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(id);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="bg-surface-900 border border-surface-800 rounded-2xl overflow-hidden flex flex-col shadow-sm">
      {/* Header & Filter Controls */}
      <div className="p-4 sm:p-5 border-b border-surface-800 space-y-3 shrink-0 bg-surface-900">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-sky-950 border border-sky-800 flex items-center justify-center text-sky-400 shrink-0">
              <Layers className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <h3 className="text-xs sm:text-base font-semibold text-surface-100 truncate">
                Evidence Sources & Grounding Registry ({findings.length})
              </h3>
              <p className="text-[10px] sm:text-[11px] text-surface-400 truncate">
                Immutable, cited tool artifacts produced by Data Investigator and Knowledge Agent
              </p>
            </div>
          </div>
          <Badge variant="purple" size="xs" className="self-start sm:self-center shrink-0">
            Grounding Plane
          </Badge>
        </div>

        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 pt-1">
          {/* Search bar */}
          <div className="relative flex-1">
            <Search className="w-3.5 h-3.5 text-surface-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Filter claims, SQL template keys, playbook titles..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 bg-surface-950 border border-surface-750 rounded-lg text-xs text-surface-200 placeholder:text-surface-500 focus:outline-none focus:border-brand-500"
            />
          </div>

          {/* Type Filter Buttons */}
          <div className="flex items-center bg-surface-950 p-1 rounded-lg border border-surface-800 shrink-0 overflow-x-auto">
            <button
              type="button"
              onClick={() => setFilterType("all")}
              className={`px-2.5 sm:px-3 py-1 text-xs rounded-md font-medium transition-all shrink-0 ${
                filterType === "all"
                  ? "bg-brand-600 text-white shadow-sm"
                  : "text-surface-400 hover:text-surface-200"
              }`}
            >
              All ({findings.length})
            </button>
            <button
              type="button"
              onClick={() => setFilterType("sql")}
              className={`flex items-center gap-1.5 px-2.5 sm:px-3 py-1 text-xs rounded-md font-medium transition-all shrink-0 ${
                filterType === "sql"
                  ? "bg-sky-600 text-white shadow-sm"
                  : "text-surface-400 hover:text-surface-200"
              }`}
            >
              <Database className="w-3 h-3" />
              <span>SQL ({sqlCount})</span>
            </button>
            <button
              type="button"
              onClick={() => setFilterType("rag")}
              className={`flex items-center gap-1.5 px-2.5 sm:px-3 py-1 text-xs rounded-md font-medium transition-all shrink-0 ${
                filterType === "rag"
                  ? "bg-purple-600 text-white shadow-sm"
                  : "text-surface-400 hover:text-surface-200"
              }`}
            >
              <FileText className="w-3 h-3" />
              <span>Playbooks ({ragCount})</span>
            </button>
          </div>
        </div>
      </div>

      {/* Findings List & Cards */}
      <div className="p-3.5 sm:p-5 space-y-3.5 sm:space-y-4 overflow-y-auto max-h-[700px]">
        {filteredFindings.length === 0 ? (
          <div className="text-center py-12 text-surface-500 text-xs">
            No evidence findings match the selected filters.
          </div>
        ) : (
          filteredFindings.map((finding) => {
            const isSql = finding.source_id.startsWith("sql_");
            const isExpanded =
              expandedSourceId === finding.source_id || selectedSourceId === finding.source_id;

            return (
              <div
                key={finding.id || finding.source_id}
                id={`source-${finding.source_id}`}
                className={`rounded-xl border transition-all ${
                  isExpanded
                    ? "bg-surface-950 border-brand-500/80 shadow-md ring-1 ring-brand-500/20"
                    : "bg-surface-950/80 border-surface-800 hover:border-surface-700"
                }`}
              >
                {/* Header item */}
                <div
                  className="p-3.5 sm:p-4 flex items-start justify-between gap-2.5 sm:gap-3 cursor-pointer select-none"
                  onClick={() => {
                    setExpandedSourceId(isExpanded ? null : finding.source_id);
                    onSelectSource?.(finding.source_id);
                  }}
                >
                  <div className="flex items-start gap-2.5 sm:gap-3 flex-1 min-w-0">
                    <div
                      className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 mt-0.5 ${
                        isSql
                          ? "bg-sky-950 border border-sky-800 text-sky-400"
                          : "bg-purple-950 border border-purple-800 text-purple-400"
                      }`}
                    >
                      {isSql ? <Database className="w-4 h-4" /> : <FileText className="w-4 h-4" />}
                    </div>

                    <div className="space-y-1 min-w-0 flex-1">
                      <div className="flex items-center gap-1.5 sm:gap-2 flex-wrap">
                        <span className="font-mono text-xs font-semibold text-surface-100">
                          {finding.source_id}
                        </span>
                        <Badge variant={isSql ? "info" : "purple"} size="xs">
                          {isSql ? "SQL Tool" : "Playbook RAG"}
                        </Badge>
                        <Badge variant="default" size="xs">
                          {Math.round(finding.confidence * 100)}% Conf
                        </Badge>
                      </div>

                      <p className="text-xs sm:text-sm text-surface-200 font-medium leading-snug break-words">
                        {finding.claim}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5 shrink-0">
                    <button
                      type="button"
                      onClick={(e) => handleCopy(finding.source_id, e)}
                      className="p-1.5 rounded-md hover:bg-surface-800 text-surface-400 hover:text-surface-200 transition-colors"
                      title="Copy Source ID"
                    >
                      {copiedId === finding.source_id ? (
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                      ) : (
                        <Copy className="w-3.5 h-3.5" />
                      )}
                    </button>
                    {isExpanded ? (
                      <ChevronDown className="w-4 h-4 text-surface-400" />
                    ) : (
                      <ChevronRight className="w-4 h-4 text-surface-400" />
                    )}
                  </div>
                </div>

                {/* Expanded Details Body */}
                {isExpanded && (
                  <div className="px-3.5 pb-3.5 sm:px-4 sm:pb-4 pt-2 border-t border-surface-850 space-y-3 text-xs animate-fadeIn">
                    {finding.sources.map((source, sIdx) => (
                      <div
                        key={sIdx}
                        className="p-3 sm:p-3.5 rounded-lg bg-surface-900 border border-surface-800 space-y-2.5"
                      >
                        {/* SQL Template Info */}
                        {source.template_key && (
                          <div className="flex flex-col sm:flex-row sm:items-center justify-between text-[11px] pb-2 border-b border-surface-800 gap-1">
                            <span className="text-surface-400 truncate">
                              Template:{" "}
                              <code className="text-sky-300 font-mono font-semibold">
                                {source.template_key}
                              </code>
                            </span>
                            {source.row_count !== undefined && (
                              <span className="text-surface-400 font-mono shrink-0">
                                Rows: <strong className="text-surface-200">{source.row_count}</strong>
                              </span>
                            )}
                          </div>
                        )}

                        {/* RAG Doc Info */}
                        {source.title && (
                          <div className="flex flex-col sm:flex-row sm:items-center justify-between text-[11px] pb-2 border-b border-surface-800 gap-1">
                            <span className="text-surface-300 font-semibold flex items-center gap-1.5 truncate">
                              <FileText className="w-3.5 h-3.5 text-purple-400 shrink-0" />
                              <span className="truncate">{source.title}</span>
                            </span>
                            {source.score !== undefined && (
                              <span className="text-surface-400 font-mono shrink-0">
                                Match:{" "}
                                <strong className="text-purple-300">
                                  {Math.round(source.score * 100)}%
                                </strong>
                              </span>
                            )}
                          </div>
                        )}

                        {/* Text Excerpt */}
                        {source.excerpt && (
                          <div className="p-2.5 rounded bg-surface-950 border border-surface-850 font-sans text-surface-300 text-[11px] leading-relaxed break-words">
                            {source.excerpt}
                          </div>
                        )}

                        {/* Formatted Rows Table if SQL sample_rows */}
                        {source.sample_rows && source.sample_rows.length > 0 && (
                          <div className="space-y-1.5">
                            <span className="text-[10px] uppercase font-mono tracking-wider text-surface-400 block font-semibold">
                              Sample Query Rows ({source.sample_rows.length})
                            </span>
                            <div className="overflow-x-auto rounded border border-surface-800 bg-surface-950 max-h-48 -mx-1 sm:mx-0">
                              <table className="w-full text-left text-[11px] border-collapse min-w-[240px]">
                                <thead>
                                  <tr className="border-b border-surface-800 bg-surface-900/80 text-surface-400 font-mono">
                                    {Object.keys(source.sample_rows[0]).map((col) => (
                                      <th key={col} className="py-1.5 px-2.5 font-medium whitespace-nowrap">
                                        {col}
                                      </th>
                                    ))}
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-surface-850 font-mono text-surface-200">
                                  {source.sample_rows.slice(0, 5).map((row: Record<string, any>, rIdx: number) => (
                                    <tr key={rIdx} className="hover:bg-surface-900/40">
                                      {Object.values(row).map((val: any, vIdx: number) => (
                                        <td key={vIdx} className="py-1.5 px-2.5 whitespace-nowrap">
                                          {typeof val === "number"
                                            ? val.toLocaleString()
                                            : String(val ?? "")}
                                        </td>
                                      ))}
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
