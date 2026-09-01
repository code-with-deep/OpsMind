import { useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import {
  Activity,
  Brain,
  History,
  Key,
  Menu,
  PlusCircle,
  Wrench,
  X,
  Compass,
} from "lucide-react";
import { api } from "../../lib/api";
import { routes } from "../../lib/routes";
import { Badge } from "../common/Badge";
import { Button } from "../common/Button";
import { OpsMindLogo } from "../common/OpsMindLogo";
import { ApiKeyModal } from "./ApiKeyModal";

interface HeaderProps {
  onNewInvestigationClick: () => void;
  investigationCount?: number;
  approvedCount?: number;
}

function navClassName(isActive: boolean) {
  return `flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
    isActive
      ? "bg-accent-500 text-surface-950 shadow-glow-accent"
      : "text-surface-400 hover:text-surface-100 hover:bg-surface-800/60"
  }`;
}

function mobileNavClassName(isActive: boolean) {
  return `w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-medium transition-colors ${
    isActive ? "bg-accent-500 text-surface-950" : "text-surface-300 hover:bg-surface-800"
  }`;
}

export function Header({
  onNewInvestigationClick,
  investigationCount = 0,
  approvedCount = 0,
}: HeaderProps) {
  const location = useLocation();
  const [isKeyModalOpen, setIsKeyModalOpen] = useState(false);
  const [systemReady, setSystemReady] = useState<boolean | null>(null);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [location.pathname]);

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

  return (
    <header className="sticky top-0 z-40 border-b border-surface-800/40 bg-[#030712]/85 backdrop-blur-xl">
      <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-14 sm:h-16 gap-2">
          <div className="flex items-center gap-2 sm:gap-4 min-w-0">
            <NavLink
              to={routes.home}
              className="flex items-center gap-2 sm:gap-2.5 text-left group focus:outline-none min-w-0"
            >
              <OpsMindLogo className="w-8 h-8 sm:w-9 sm:h-9 shrink-0 group-hover:scale-105 transition-transform" />
              <div className="min-w-0">
                <div className="flex items-center gap-1.5 sm:gap-2">
                  <span className="font-app-heading text-base sm:text-lg text-white tracking-tight truncate">
                    OpsMind
                  </span>
                  <Badge variant="success" size="xs" className="hidden sm:inline-flex">
                    Console
                  </Badge>
                </div>
                <p className="text-[10px] sm:text-[11px] text-surface-500 -mt-0.5 hidden sm:block truncate">
                  Operations Intelligence
                </p>
              </div>
            </NavLink>

            <div className="hidden xl:flex items-center gap-3 pl-4 border-l border-surface-800 text-xs text-surface-400">
              <div>
                Runs:{" "}
                <span className="text-surface-200 font-mono font-medium">{investigationCount}</span>
              </div>
              <div>
                Approved:{" "}
                <span className="text-accent-400 font-mono font-medium">{approvedCount}</span>
              </div>
            </div>
          </div>

          <nav className="hidden md:flex items-center gap-1 landing-glass p-1 rounded-xl border border-surface-700/50">
            <NavLink to={routes.home} end className={({ isActive }) => navClassName(isActive)}>
              <Compass className="w-3.5 h-3.5" />
              <span>Home</span>
            </NavLink>

            <NavLink to={routes.console} className={({ isActive }) => navClassName(isActive)}>
              <Activity className="w-3.5 h-3.5" />
              <span>Console</span>
            </NavLink>

            <NavLink to={routes.history} className={({ isActive }) => navClassName(isActive)}>
              <History className="w-3.5 h-3.5" />
              <span>History</span>
              {investigationCount > 0 && (
                <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-surface-900/80 text-surface-300 font-mono">
                  {investigationCount}
                </span>
              )}
            </NavLink>

            <NavLink to={routes.cases} className={({ isActive }) => navClassName(isActive)}>
              <Brain className="w-3.5 h-3.5" />
              <span>Cases</span>
              {approvedCount > 0 && (
                <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-accent-950 text-accent-300 font-mono border border-accent-800/60">
                  {approvedCount}
                </span>
              )}
            </NavLink>

            <NavLink to={routes.tools} className={({ isActive }) => navClassName(isActive)}>
              <Wrench className="w-3.5 h-3.5" />
              <span>Tools</span>
            </NavLink>
          </nav>

          <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
            <div className="hidden md:flex items-center">
              {systemReady === true ? (
                <Badge variant="success" size="sm" dot>
                  API Ready
                </Badge>
              ) : systemReady === false ? (
                <Badge variant="error" size="sm" dot>
                  API Offline
                </Badge>
              ) : (
                <Badge variant="default" size="sm" dot>
                  Checking...
                </Badge>
              )}
            </div>

            <Button
              variant="outline"
              size="sm"
              icon={<Key className="w-3.5 h-3.5 text-accent-400" />}
              onClick={() => setIsKeyModalOpen(true)}
              title="Configure API Key Auth"
              className="min-h-10 px-2.5 sm:px-3"
            >
              <span className="hidden sm:inline">Auth</span>
            </Button>

            <Button
              variant="accent"
              size="sm"
              icon={<PlusCircle className="w-3.5 h-3.5 sm:w-4 sm:h-4" />}
              onClick={onNewInvestigationClick}
              className="min-h-10 px-3 sm:px-3.5"
            >
              <span className="hidden sm:inline">New Investigation</span>
              <span className="sm:hidden font-semibold">New</span>
            </Button>

            <button
              type="button"
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              className="md:hidden touch-target rounded-lg bg-surface-900/80 border border-surface-700 text-surface-300 hover:text-white focus:outline-none"
              aria-label="Toggle navigation menu"
            >
              {isMobileMenuOpen ? (
                <X className="w-4 h-4 sm:w-5 sm:h-5" />
              ) : (
                <Menu className="w-4 h-4 sm:w-5 sm:h-5" />
              )}
            </button>
          </div>
        </div>

        {isMobileMenuOpen && (
          <div className="md:hidden py-3 border-t border-surface-800 space-y-1 animate-slide-up pb-[max(0.75rem,env(safe-area-inset-bottom))]">
            <div className="px-3 py-1.5 mb-2 flex items-center justify-between app-panel text-xs">
              <span className="text-surface-400">API Status</span>
              {systemReady === true ? (
                <span className="text-accent-400 font-medium">Connected</span>
              ) : systemReady === false ? (
                <span className="text-rose-400 font-medium">Offline</span>
              ) : (
                <span className="text-surface-400 font-medium">Checking...</span>
              )}
            </div>

            <NavLink to={routes.home} end className={({ isActive }) => mobileNavClassName(isActive)}>
              <span className="flex items-center gap-2.5">
                <Compass className="w-4 h-4" /> Home
              </span>
            </NavLink>

            <NavLink to={routes.console} className={({ isActive }) => mobileNavClassName(isActive)}>
              <span className="flex items-center gap-2.5">
                <Activity className="w-4 h-4" /> Console
              </span>
            </NavLink>

            <NavLink to={routes.history} className={({ isActive }) => mobileNavClassName(isActive)}>
              <span className="flex items-center gap-2.5">
                <History className="w-4 h-4" /> History
              </span>
              <span className="font-mono text-xs px-2 py-0.5 rounded-full bg-surface-900 text-surface-200">
                {investigationCount}
              </span>
            </NavLink>

            <NavLink to={routes.cases} className={({ isActive }) => mobileNavClassName(isActive)}>
              <span className="flex items-center gap-2.5">
                <Brain className="w-4 h-4" /> Case Memory
              </span>
              <span className="font-mono text-xs px-2 py-0.5 rounded-full bg-accent-950 text-accent-300 border border-accent-800/60">
                {approvedCount}
              </span>
            </NavLink>

            <NavLink to={routes.tools} className={({ isActive }) => mobileNavClassName(isActive)}>
              <span className="flex items-center gap-2.5">
                <Wrench className="w-4 h-4" /> SQL Tools Lab
              </span>
            </NavLink>
          </div>
        )}
      </div>

      <ApiKeyModal isOpen={isKeyModalOpen} onClose={() => setIsKeyModalOpen(false)} />
    </header>
  );
}
