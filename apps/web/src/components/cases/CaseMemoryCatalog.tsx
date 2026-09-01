import { useEffect, useState } from "react";
import { CaseSummaryItem } from "../../types";
import { api } from "../../lib/api";
import { formatDate } from "../../lib/utils";
import { Badge } from "../common/Badge";
import { Button } from "../common/Button";
import { PageHeader } from "../common/PageHeader";
import { EmptyState, ListCard, SearchBar } from "../common/AppUI";
import { Brain, ExternalLink, RefreshCw } from "lucide-react";

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
    <div className="space-y-5">
      <PageHeader
        icon={<Brain className="w-5 h-5" />}
        title="Case Memory"
        description="Approved investigations saved for future triage"
        badge={
          <Badge variant="success" size="xs">
            {cases.length} cases
          </Badge>
        }
        action={
          <Button
            variant="outline"
            size="sm"
            icon={<RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />}
            onClick={loadCases}
          >
            Refresh
          </Button>
        }
      />

      <SearchBar
        value={search}
        onChange={setSearch}
        placeholder="Search by title, SKU, driver, or keyword..."
      />

      {loading ? (
        <div className="text-center py-16 text-surface-400 text-sm animate-pulse">
          Loading case memory...
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={<Brain className="w-10 h-10" />}
          title="No approved cases yet"
          description='Approve an investigation from the Console review panel to save it here for future reference.'
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {filtered.map((item) => (
            <ListCard key={item.id}>
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-2">
                  <h3 className="font-app-heading text-base text-white leading-snug">{item.title}</h3>
                  <Badge variant="success" size="xs" className="shrink-0">
                    Approved
                  </Badge>
                </div>

                <p className="text-sm text-surface-300 leading-relaxed">{item.summary}</p>

                <blockquote className="text-xs text-surface-400 italic border-l-2 border-accent-800/50 pl-3 leading-relaxed">
                  {item.question}
                </blockquote>

                {item.drivers && item.drivers.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {item.drivers.map((d, dIdx) => (
                      <Badge key={dIdx} variant="success" size="xs">
                        {d}
                      </Badge>
                    ))}
                  </div>
                )}

                <div className="flex items-center justify-between pt-3 border-t border-surface-800/60">
                  <span className="text-xs text-surface-500">{formatDate(item.created_at)}</span>
                  <Button
                    variant="outline"
                    size="xs"
                    icon={<ExternalLink className="w-3 h-3 text-accent-400" />}
                    onClick={() => onSelectInvestigation(item.investigation_id)}
                  >
                    View Run
                  </Button>
                </div>
              </div>
            </ListCard>
          ))}
        </div>
      )}
    </div>
  );
}
