import { useEffect, useState } from "react";
import { SqlTemplate } from "../../types";
import { api } from "../../lib/api";
import { Badge } from "../common/Badge";
import {
  Search,
  Wrench,
  Table,
} from "lucide-react";

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
    <div className="space-y-4 sm:space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-surface-900 border border-surface-800 p-4 sm:p-5 rounded-2xl shadow-sm">
        <div className="flex items-center gap-2.5 sm:gap-3 min-w-0">
          <div className="w-9 h-9 sm:w-10 sm:h-10 rounded-xl bg-sky-950 border border-sky-800 flex items-center justify-center text-sky-400 shrink-0">
            <Wrench className="w-4 h-4 sm:w-5 sm:h-5" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="text-sm sm:text-base font-bold text-surface-100 truncate">
                Allowlisted SQL Tools Catalog (P2 Grounding)
              </h2>
              <Badge variant="info" size="xs" className="shrink-0">
                {templates.length} Safe Templates
              </Badge>
            </div>
            <p className="text-[10px] sm:text-xs text-surface-400 mt-0.5 truncate">
              Strictly parameterized read-only queries callable by the Data Investigator agent
            </p>
          </div>
        </div>
      </div>

      {/* Search Input */}
      <div className="relative">
        <Search className="w-4 h-4 text-surface-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
        <input
          type="text"
          placeholder="Filter SQL templates by key, table, or description..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-10 pr-4 py-2 bg-surface-900 border border-surface-750 rounded-xl text-xs sm:text-sm text-surface-100 placeholder:text-surface-500 focus:outline-none focus:border-brand-500"
        />
      </div>

      {/* Templates Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 sm:gap-4">
        {filtered.map((t) => {
          const paramKeys = t.parameters ? Object.keys(t.parameters) : [];
          return (
            <div
              key={t.key}
              className="p-4 sm:p-5 rounded-2xl bg-surface-900 border border-surface-800 space-y-3 hover:border-surface-700 transition-all shadow-sm flex flex-col justify-between"
            >
              <div className="space-y-2">
                <div className="flex items-start justify-between gap-2">
                  <code className="text-xs sm:text-sm font-mono font-bold text-sky-300 block break-all">
                    {t.key}
                  </code>
                  <Badge variant="outline" size="xs" className="shrink-0">
                    Read-Only
                  </Badge>
                </div>
                <p className="text-xs text-surface-300 leading-snug break-words">{t.description}</p>
              </div>

              <div className="space-y-2 pt-2 border-t border-surface-850 text-xs">
                <div className="flex items-center gap-1.5 text-surface-400">
                  <Table className="w-3.5 h-3.5 text-surface-500 shrink-0" />
                  <span>Target Table:</span>
                  <span className="font-mono text-surface-200 font-semibold">{t.table}</span>
                </div>

                {paramKeys.length > 0 && (
                  <div className="space-y-1 pt-1">
                    <span className="text-[10px] uppercase font-mono tracking-wider text-surface-500 font-semibold block">
                      Parameters & Types
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {paramKeys.map((p) => (
                        <span
                          key={p}
                          className="px-2 py-0.5 rounded bg-surface-950 border border-surface-800 text-[10px] sm:text-[11px] font-mono text-surface-300"
                        >
                          :{p} <span className="text-surface-500 font-sans">({t.parameters[p]})</span>
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
