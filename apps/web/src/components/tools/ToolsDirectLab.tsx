import { useEffect, useState } from "react";
import { SqlTemplate } from "../../types";
import { api } from "../../lib/api";
import { Badge } from "../common/Badge";
import { PageHeader } from "../common/PageHeader";
import { EmptyState, ListCard, SearchBar } from "../common/AppUI";
import { Wrench, Table } from "lucide-react";

export function ToolsDirectLab() {
  const [templates, setTemplates] = useState<SqlTemplate[]>([]);
  const [search, setSearch] = useState("");

  useEffect(() => {
    const loadTemplates = async () => {
      try {
        const res = await api.getSqlTemplates();
        setTemplates(res.templates || []);
      } catch (err) {
        console.error("Failed to fetch templates:", err);
      }
    };
    loadTemplates();
  }, []);

  const filtered = templates.filter((t) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      t.key.toLowerCase().includes(q) ||
      t.description.toLowerCase().includes(q) ||
      t.table.toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-5">
      <PageHeader
        icon={<Wrench className="w-5 h-5" />}
        title="SQL Tools Lab"
        description="Read-only query templates available to the Data Investigator"
        badge={
          <Badge variant="info" size="xs">
            {templates.length} templates
          </Badge>
        }
      />

      <SearchBar
        value={search}
        onChange={setSearch}
        placeholder="Filter by template name, table, or description..."
      />

      {filtered.length === 0 ? (
        <EmptyState
          icon={<Wrench className="w-10 h-10" />}
          title="No templates found"
          description="Try a different search term, or check that the API is running."
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {filtered.map((t) => {
          const paramKeys = t.parameters ? Object.keys(t.parameters) : [];
          return (
            <ListCard key={t.key}>
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-2">
                  <code className="text-sm font-mono font-semibold text-accent-300 break-all">
                    {t.key}
                  </code>
                  <Badge variant="outline" size="xs" className="shrink-0">
                    Read-only
                  </Badge>
                </div>

                <p className="text-sm text-surface-300 leading-relaxed">{t.description}</p>

                <div className="flex items-center gap-2 text-xs text-surface-400 pt-2 border-t border-surface-800/50">
                  <Table className="w-3.5 h-3.5 shrink-0" />
                  <span>Table:</span>
                  <span className="font-mono text-surface-200">{t.table}</span>
                </div>

                {paramKeys.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {paramKeys.map((p) => (
                      <span
                        key={p}
                        className="px-2 py-0.5 rounded-md bg-surface-950 border border-surface-800 text-[11px] font-mono text-surface-300"
                      >
                        :{p}
                        <span className="text-surface-500 font-sans ml-1">({t.parameters[p]})</span>
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </ListCard>
          );
        })}
        </div>
      )}
    </div>
  );
}
