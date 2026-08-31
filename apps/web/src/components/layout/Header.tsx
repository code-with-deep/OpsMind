import { useEffect, useState } from "react";
import {
  Activity,
  Brain,
  History,
  Key,
  Menu,
  PlusCircle,
  Sparkles,
  Wrench,
  X,
  Compass,
} from "lucide-react";
import { api } from "../../lib/api";
import { Badge } from "../common/Badge";
import { Button } from "../common/Button";
import { ApiKeyModal } from "./ApiKeyModal";

export type ActiveTab = "overview" | "investigation" | "history" | "cases" | "tools";

interface HeaderProps {
  activeTab: ActiveTab;
  onTabChange: (tab: ActiveTab) => void;
  onNewInvestigationClick: () => void;
  investigationCount?: number;
  approvedCount?: number;
}

export function Header({
  activeTab,
  onTabChange,
  onNewInvestigationClick,
  investigationCount = 0,
  approvedCount = 0,
}: HeaderProps) {
  const [isKeyModalOpen, setIsKeyModalOpen] = useState(false);
  const [systemReady, setSystemReady] = useState<boolean | null>(null);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  useEffect(() => {
    let mounted = true;
    const checkSystem = async () => {
      try {
        await api.checkReady();
        if (mounted) setSystemReady(true);
      } catch {
        if (mounted) setSystemReady(false);
      }
    };
    checkSystem();
    const interval = setInterval(checkSystem, 15000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  const handleTabClick = (tab: ActiveTab) => {
    onTabChange(tab);
    setIsMobileMenuOpen(false);
  };

  return (
    <header className="sticky top-0 z-40 bg-surface-950/95 backdrop-blur-md border-b border-surface-800/80 shadow-sm">
      <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-14 sm:h-16 gap-2">
          {/* Logo & Product Badge */}
          <div className="flex items-center gap-2 sm:gap-4 min-w-0">
            <button
              type="button"
              onClick={() => onTabChange("overview")}
              className="flex items-center gap-2 sm:gap-2.5 text-left group focus:outline-none min-w-0"
            >
              <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-xl bg-gradient-to-br from-brand-500 to-indigo-700 flex items-center justify-center shadow-lg shadow-brand-500/20 border border-brand-400/30 group-hover:scale-105 transition-transform shrink-0">
                <Sparkles className="w-4 h-4 sm:w-5 sm:h-5 text-white" />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-1.5 sm:gap-2">
                  <span className="font-bold text-base sm:text-lg text-surface-100 tracking-tight group-hover:text-white transition-colors truncate">
                    OpsMind
                  </span>
                  <Badge variant="purple" size="xs" className="hidden xs:inline-flex">
                    v0.8
                  </Badge>
                </div>
                <p className="text-[10px] sm:text-[11px] text-surface-400 -mt-0.5 font-medium hidden sm:block truncate">
                  Self-Correcting Operations Intelligence
                </p>
              </div>
            </button>

            {/* Quick Stats Pill (Large Screen) */}
            <div className="hidden xl:flex items-center gap-3 pl-4 border-l border-surface-800 text-xs text-surface-400">
              <div>
                Runs: <span className="text-surface-200 font-mono font-medium">{investigationCount}</span>
              </div>
              <div>
                Approved Cases:{" "}
                <span className="text-emerald-400 font-mono font-medium">{approvedCount}</span>
              </div>
            </div>
          </div>

          {/* Desktop Navigation Tabs (Hidden on <1024px) */}
          <nav className="hidden lg:flex items-center gap-1 bg-surface-900/90 p-1 rounded-xl border border-surface-800/80 shadow-inner">
            <button
              type="button"
              onClick={() => handleTabClick("overview")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                activeTab === "overview"
                  ? "bg-brand-600 text-white shadow-sm"
                  : "text-surface-400 hover:text-surface-200 hover:bg-surface-800/60"
              }`}
            >
              <Compass className="w-3.5 h-3.5" />
              <span>Overview</span>
            </button>

            <button
              type="button"
              onClick={() => handleTabClick("investigation")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                activeTab === "investigation"
                  ? "bg-brand-600 text-white shadow-sm"
                  : "text-surface-400 hover:text-surface-200 hover:bg-surface-800/60"
              }`}
            >
              <Activity className="w-3.5 h-3.5" />
              <span>Console</span>
            </button>

            <button
              type="button"
              onClick={() => handleTabClick("history")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                activeTab === "history"
                  ? "bg-brand-600 text-white shadow-sm"
                  : "text-surface-400 hover:text-surface-200 hover:bg-surface-800/60"
              }`}
            >
              <History className="w-3.5 h-3.5" />
              <span>History</span>
              {investigationCount > 0 && (
                <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-surface-800 text-surface-300 font-mono">
                  {investigationCount}
                </span>
              )}
            </button>

            <button
              type="button"
              onClick={() => handleTabClick("cases")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                activeTab === "cases"
                  ? "bg-brand-600 text-white shadow-sm"
                  : "text-surface-400 hover:text-surface-200 hover:bg-surface-800/60"
              }`}
            >
              <Brain className="w-3.5 h-3.5" />
              <span>Case Memory</span>
              {approvedCount > 0 && (
                <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-emerald-950 text-emerald-300 font-mono border border-emerald-800/60">
                  {approvedCount}
                </span>
              )}
            </button>

            <button
              type="button"
              onClick={() => handleTabClick("tools")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                activeTab === "tools"
                  ? "bg-brand-600 text-white shadow-sm"
                  : "text-surface-400 hover:text-surface-200 hover:bg-surface-800/60"
              }`}
            >
              <Wrench className="w-3.5 h-3.5" />
              <span>SQL Tools Lab</span>
            </button>
          </nav>

          {/* Right Action Bar */}
          <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
            {/* System Readiness Pill */}
            <div className="hidden md:flex items-center">
              {systemReady === true ? (
                <Badge variant="success" size="sm" dot>
                  API Ready
                </Badge>
              ) : systemReady === false ? (
                <Badge variant="error" size="sm" dot>
                  API Disconnected
                </Badge>
              ) : (
                <Badge variant="default" size="sm" dot>
                  Checking...
                </Badge>
              )}
            </div>

            {/* API Key Modal Button */}
            <Button
              variant="outline"
              size="sm"
              icon={<Key className="w-3.5 h-3.5 text-brand-400" />}
              onClick={() => setIsKeyModalOpen(true)}
              title="Configure API Key Auth"
              className="px-2 sm:px-2.5"
            >
              <span className="hidden sm:inline">Auth</span>
            </Button>

            {/* New Investigation Button */}
            <Button
              variant="primary"
              size="sm"
              icon={<PlusCircle className="w-3.5 h-3.5 sm:w-4 sm:h-4" />}
              onClick={onNewInvestigationClick}
              className="px-2.5 sm:px-3.5"
            >
              <span className="hidden sm:inline">New Investigation</span>
              <span className="sm:hidden font-semibold">New</span>
            </Button>

            {/* Mobile Menu Toggle Button */}
            <button
              type="button"
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              className="lg:hidden p-2 rounded-lg bg-surface-900 border border-surface-800 text-surface-300 hover:text-white focus:outline-none"
              aria-label="Toggle navigation menu"
            >
              {isMobileMenuOpen ? <X className="w-4 h-4 sm:w-5 sm:h-5" /> : <Menu className="w-4 h-4 sm:w-5 sm:h-5" />}
            </button>
          </div>
        </div>

        {/* Mobile Navigation Drawer */}
        {isMobileMenuOpen && (
          <div className="lg:hidden py-3 border-t border-surface-800 space-y-1 animate-slide-up">
            {/* System Status on Mobile */}
            <div className="px-3 py-1.5 mb-2 flex items-center justify-between bg-surface-900/60 rounded-lg text-xs">
              <span className="text-surface-400">System Status:</span>
              {systemReady === true ? (
                <span className="text-emerald-400 font-medium flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" /> API Connected
                </span>
              ) : systemReady === false ? (
                <span className="text-rose-400 font-medium flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-rose-400" /> API Offline
                </span>
              ) : (
                <span className="text-surface-400 font-medium">Checking...</span>
              )}
            </div>

            <button
              type="button"
              onClick={() => handleTabClick("overview")}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-medium transition-colors ${
                activeTab === "overview" ? "bg-brand-600 text-white" : "text-surface-300 hover:bg-surface-800"
              }`}
            >
              <span className="flex items-center gap-2.5">
                <Compass className="w-4 h-4" /> Overview & Product Story
              </span>
            </button>

            <button
              type="button"
              onClick={() => handleTabClick("investigation")}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-medium transition-colors ${
                activeTab === "investigation" ? "bg-brand-600 text-white" : "text-surface-300 hover:bg-surface-800"
              }`}
            >
              <span className="flex items-center gap-2.5">
                <Activity className="w-4 h-4" /> Live Investigation Console
              </span>
            </button>

            <button
              type="button"
              onClick={() => handleTabClick("history")}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-medium transition-colors ${
                activeTab === "history" ? "bg-brand-600 text-white" : "text-surface-300 hover:bg-surface-800"
              }`}
            >
              <span className="flex items-center gap-2.5">
                <History className="w-4 h-4" /> Investigation History
              </span>
              <span className="font-mono text-xs px-2 py-0.5 rounded-full bg-surface-800 text-surface-200">
                {investigationCount}
              </span>
            </button>

            <button
              type="button"
              onClick={() => handleTabClick("cases")}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-medium transition-colors ${
                activeTab === "cases" ? "bg-brand-600 text-white" : "text-surface-300 hover:bg-surface-800"
              }`}
            >
              <span className="flex items-center gap-2.5">
                <Brain className="w-4 h-4" /> Case Memory Catalog
              </span>
              <span className="font-mono text-xs px-2 py-0.5 rounded-full bg-emerald-950 text-emerald-300 border border-emerald-800/60">
                {approvedCount}
              </span>
            </button>

            <button
              type="button"
              onClick={() => handleTabClick("tools")}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-medium transition-colors ${
                activeTab === "tools" ? "bg-brand-600 text-white" : "text-surface-300 hover:bg-surface-800"
              }`}
            >
              <span className="flex items-center gap-2.5">
                <Wrench className="w-4 h-4" /> Allowlisted SQL Tools Lab
              </span>
            </button>
          </div>
        )}
      </div>

      <ApiKeyModal
        isOpen={isKeyModalOpen}
        onClose={() => setIsKeyModalOpen(false)}
      />
    </header>
  );
}
