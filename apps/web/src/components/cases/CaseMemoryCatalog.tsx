import { useEffect, useState } from "react";
import { CaseSummaryItem } from "../../types";
import { api } from "../../lib/api";
import { formatDate } from "../../lib/utils";
import { Badge } from "../common/Badge";
import { Button } from "../common/Button";
import {
  Brain,
  Search,
  TrendingDown,
  ExternalLink,
  RefreshCw,
} from "lucide-react";

interface CaseMemoryCatalogProps {
  onSelectInvestigation: (id: string) => void;
}

export function CaseMemoryCatalog({ onSelectInvestigation }: CaseMemoryCatalogProps) {
  const [cases, setCases] = useState<CaseSummaryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  const loadCases = async () => {
    setLoading(true);
    try {
      const res = await api.getCaseMemory();
      setCases(res.cases || []);
    } catch (err) {
      console.error("Failed to load case memory:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCases();
  }, []);

  const filtered = cases.filter((c) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      c.title.toLowerCase().includes(q) ||
      c.question.toLowerCase().includes(q) ||
      c.summary.toLowerCase().includes(q) ||
      c.drivers?.some((d) => d.toLowerCase().includes(q))
    );
  });

  return (
    <div className="space-y-4 sm:space-y-5">
      {/* Catalog Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-surface-900 border border-surface-800 p-4 sm:p-5 rounded-2xl shadow-sm">
        <div className="flex items-center gap-2.5 sm:gap-3 min-w-0">
          <div className="w-9 h-9 sm:w-10 sm:h-10 rounded-xl bg-emerald-950 border border-emerald-800 flex items-center justify-center text-emerald-400 shrink-0">
            <Brain className="w-4 h-4 sm:w-5 sm:h-5" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="text-sm sm:text-base font-bold text-surface-100 truncate">
                Episodic Case Memory Catalog
              </h2>
              <Badge variant="success" size="xs" className="shrink-0">
                {cases.length} Approved Cases
              </Badge>
            </div>
            <p className="text-[10px] sm:text-xs text-surface-400 mt-0.5 truncate">
              Vector-embedded incident resolutions retrieved by Planner to accelerate root cause triage
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-center shrink-0">
          <Button
            variant="outline"
            size="sm"
            icon={<RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />}
            onClick={loadCases}
          >
            Refresh
          </Button>
        </div>
      </div>

      {/* Search Bar */}
      <div className="relative">
        <Search className="w-4 h-4 text-surface-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
        <input
          type="text"
          placeholder="Search case memory by keyword, SKU, driver (e.g. 'stockout', 'FastShip', 'earbuds')..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-10 pr-4 py-2 bg-surface-900 border border-surface-750 rounded-xl text-xs sm:text-sm text-surface-100 placeholder:text-surface-500 focus:outline-none focus:border-brand-500"
        />
      </div>

      {/* Cases List */}
      {loading ? (
        <div className="text-center py-16 text-surface-400 text-xs animate-pulse">
          Loading case memory catalog...
        </div>
      ) : filtered.length === 0 ? (
        <div className="p-8 sm:p-12 text-center bg-surface-900/60 border border-surface-800 rounded-2xl space-y-3">
          <Brain className="w-8 h-8 sm:w-10 sm:h-10 text-surface-600 mx-auto" />
          <h3 className="text-xs sm:text-sm font-semibold text-surface-200">No Approved Cases Found</h3>
          <p className="text-[11px] sm:text-xs text-surface-400 max-w-sm mx-auto leading-relaxed">
            When operators review and click <strong>"Approve"</strong> on an investigation report, it is vector-embedded into Case Memory.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 sm:gap-4">
          {filtered.map((item) => (
            <div
              key={item.id}
              className="bg-surface-900 border border-surface-800 hover:border-surface-700 p-4 sm:p-5 rounded-2xl shadow-sm space-y-3 flex flex-col justify-between transition-all group"
            >
              <div className="space-y-2.5 min-w-0">
                <div className="flex items-start justify-between gap-2">
                  <span className="font-semibold text-xs sm:text-sm text-surface-100 group-hover:text-brand-300 transition-colors truncate">
                    {item.title}
                  </span>
                  <Badge variant="success" size="xs" className="shrink-0">
                    Approved
                  </Badge>
                </div>

                <div className="p-2.5 rounded-lg bg-surface-950 border border-surface-850 text-[11px] sm:text-xs font-mono text-surface-300 break-words">
                  "{item.question}"
                </div>

                <p className="text-xs text-surface-300 leading-relaxed font-sans break-words">
                  {item.summary}
                </p>

                {item.drivers && item.drivers.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {item.drivers.map((d, dIdx) => (
                      <Badge key={dIdx} variant="purple" size="xs">
                        <TrendingDown className="w-3 h-3 text-purple-400 mr-1 shrink-0" />
                        <span className="truncate">{d}</span>
                      </Badge>
                    ))}
                  </div>
                )}
              </div>

              <div className="pt-3 border-t border-surface-800/80 flex items-center justify-between text-xs gap-2">
                <span className="text-surface-400 font-mono text-[10px] sm:text-[11px] truncate">
                  {formatDate(item.created_at)}
                </span>
                <Button
                  variant="outline"
                  size="xs"
                  icon={<ExternalLink className="w-3 h-3 text-brand-400" />}
                  onClick={() => onSelectInvestigation(item.investigation_id)}
                  className="shrink-0"
                >
                  Inspect Run
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
