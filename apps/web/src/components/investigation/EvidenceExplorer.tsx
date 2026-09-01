import { useState } from "react";
import {
  Check,
  ChevronDown,
  ChevronRight,
  Copy,
  Database,
  FileText,
  Layers,
} from "lucide-react";
import { Finding } from "../../types";
import { Badge } from "../common/Badge";
import { EmptyState, FilterPills, SearchBar, SectionCard } from "../common/AppUI";

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
    <SectionCard
      title="Evidence Explorer"
      subtitle={`${findings.length} cited sources from SQL queries and SOP playbooks`}
      icon={<Layers className="w-4 h-4" />}
      noPadding
    >
      <div className="px-5 pt-4 pb-3 space-y-3 border-b border-surface-800/50">
        <SearchBar
          value={searchQuery}
          onChange={setSearchQuery}
          placeholder="Search claims, source IDs, or playbook titles..."
        />
        <FilterPills
          value={filterType}
          onChange={(k) => setFilterType(k as typeof filterType)}
          options={[
            { key: "all", label: "All", count: findings.length },
            { key: "sql", label: "SQL", count: sqlCount },
            { key: "rag", label: "Playbooks", count: ragCount },
          ]}
        />
      </div>

      <div className="p-4 sm:p-5 space-y-3 app-scroll-panel">
        {filteredFindings.length === 0 ? (
          <EmptyState
            icon={<Layers className="w-8 h-8" />}
            title="No evidence found"
            description="Try adjusting your search or filter."
          />
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
                    ? "app-card border-accent-600/50 ring-1 ring-accent-500/20"
                    : "app-card hover:border-surface-600"
                }`}
              >
                <button
                  type="button"
                  className="w-full p-4 flex items-start justify-between gap-3 text-left"
                  onClick={() => {
                    setExpandedSourceId(isExpanded ? null : finding.source_id);
                    onSelectSource?.(finding.source_id);
                  }}
                >
                  <div className="flex items-start gap-3 flex-1 min-w-0">
                    <div
                      className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
                        isSql
                          ? "bg-sky-950/80 border border-sky-800/60 text-sky-400"
                          : "bg-purple-950/80 border border-purple-800/60 text-purple-400"
                      }`}
                    >
                      {isSql ? <Database className="w-4 h-4" /> : <FileText className="w-4 h-4" />}
                    </div>

                    <div className="space-y-1.5 min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-mono text-xs text-accent-300">{finding.source_id}</span>
                        <Badge variant={isSql ? "info" : "success"} size="xs">
                          {isSql ? "SQL" : "RAG"}
                        </Badge>
                        <span className="text-[10px] text-surface-500">
                          {Math.round(finding.confidence * 100)}% confidence
                        </span>
                      </div>
                      <p className="text-sm text-surface-100 leading-relaxed">{finding.claim}</p>
                    </div>
                  </div>

                  <div className="flex items-center gap-0.5 shrink-0">
                    <button
                      type="button"
                      onClick={(e) => handleCopy(finding.source_id, e)}
                      className="touch-target rounded-md hover:bg-surface-800 text-surface-400"
                      title="Copy source ID"
                      aria-label="Copy source ID"
                    >
                      {copiedId === finding.source_id ? (
                        <Check className="w-3.5 h-3.5 text-accent-400" />
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
                </button>

                {isExpanded && (
                  <div className="px-4 pb-4 pt-1 border-t border-surface-800/50 space-y-3">
                    {finding.sources.map((source, sIdx) => (
                      <div key={sIdx} className="app-card p-4 space-y-3 text-sm">
                        {source.template_key && (
                          <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-surface-400 pb-2 border-b border-surface-800/50">
                            <span>
                              Template:{" "}
                              <code className="text-sky-300 font-mono">{source.template_key}</code>
                            </span>
                            {source.row_count !== undefined && (
                              <span className="font-mono">{source.row_count} rows</span>
                            )}
                          </div>
                        )}

                        {source.title && (
                          <div className="flex flex-wrap items-center justify-between gap-2 text-xs pb-2 border-b border-surface-800/50">
                            <span className="text-surface-200 font-medium flex items-center gap-1.5">
                              <FileText className="w-3.5 h-3.5 text-purple-400" />
                              {source.title}
                            </span>
                            {source.score !== undefined && (
                              <span className="text-surface-400 font-mono">
                                {Math.round(source.score * 100)}% match
                              </span>
                            )}
                          </div>
                        )}

                        {source.excerpt && (
                          <p className="text-sm text-surface-300 leading-relaxed">{source.excerpt}</p>
                        )}

                        {source.sample_rows && source.sample_rows.length > 0 && (
                          <div className="overflow-x-auto rounded-lg border border-surface-800 max-h-48">
                            <table className="w-full text-left text-xs">
                              <thead>
                                <tr className="border-b border-surface-800 bg-surface-900/80 text-surface-400">
                                  {Object.keys(source.sample_rows[0]).map((col) => (
                                    <th key={col} className="py-2 px-3 font-mono whitespace-nowrap">
                                      {col}
                                    </th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-surface-800/50 font-mono text-surface-200">
                                {source.sample_rows.slice(0, 5).map((row: Record<string, unknown>, rIdx: number) => (
                                  <tr key={rIdx}>
                                    {Object.values(row).map((val, vIdx) => (
                                      <td key={vIdx} className="py-2 px-3 whitespace-nowrap">
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
    </SectionCard>
  );
}
