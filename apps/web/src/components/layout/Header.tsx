import { useEffect, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import {
  Activity,
  Brain,
  History,
  LogIn,
  LogOut,
  Menu,
  PlusCircle,
  Settings2,
  X,
  Compass,
} from "lucide-react";
import { api, clearSession, getAccessToken, getStoredUser } from "../../lib/api";
import { routes } from "../../lib/routes";
import { Button } from "../common/Button";
import { OpsMindLogo } from "../common/OpsMindLogo";
import { NotificationBell } from "./NotificationBell";

interface HeaderProps {
  onNewInvestigationClick: () => void;
  investigationCount?: number;
  approvedCount?: number;
}

function navLink(isActive: boolean) {
  return [
    "relative flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium whitespace-nowrap transition-all duration-150",
    isActive
      ? "bg-accent-500 text-surface-950 shadow-sm"
      : "text-surface-400 hover:text-surface-100 hover:bg-surface-800/50",
  ].join(" ");
}

function mobileNavLink(isActive: boolean) {
  return [
    "w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
    isActive ? "bg-accent-500 text-surface-950" : "text-surface-300 hover:bg-surface-800/60",
  ].join(" ");
}

/** Small pill badge used for counts inside nav links */
function NavCount({ count, active }: { count: number; active: boolean }) {
  if (count === 0) return null;
  return (
    <span
      className={[
        "min-w-[18px] h-[18px] flex items-center justify-center rounded-full text-[10px] font-bold tabular-nums px-1",
        active
          ? "bg-surface-950/25 text-surface-950"
          : "bg-surface-800 text-surface-300",
      ].join(" ")}
    >
      {count}
    </span>
  );
}

/** Pulsing API status dot */
function ApiDot({ ready }: { ready: boolean | null }) {
  const title =
    ready === true ? "API Ready" : ready === false ? "API Offline" : "Checking API…";
  const color =
    ready === true
      ? "bg-emerald-400"
      : ready === false
      ? "bg-rose-400"
      : "bg-surface-500";
  return (
    <span title={title} className="relative flex items-center justify-center w-5 h-5 shrink-0">
      {ready === true && (
        <span className="absolute inline-flex w-full h-full rounded-full bg-emerald-400 opacity-30 animate-ping" />
      )}
      <span className={`relative inline-flex rounded-full w-2 h-2 ${color}`} />
    </span>
  );
}

/** User avatar circle with first-letter initial */
function UserAvatar({ name }: { name: string }) {
  const initial = (name || "?")[0].toUpperCase();
  return (
    <span className="w-7 h-7 rounded-full bg-accent-800/60 border border-accent-600/40 flex items-center justify-center text-xs font-bold text-accent-200 shrink-0 select-none">
      {initial}
    </span>
  );
}

export function Header({
  onNewInvestigationClick,
  investigationCount = 0,
  approvedCount = 0,
}: HeaderProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const [systemReady, setSystemReady] = useState<boolean | null>(null);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const sessionUser = getStoredUser();
  const hasJwt = Boolean(getAccessToken());

  // Display name: prefer tenant name, fall back to email prefix
  const displayName = sessionUser?.tenant?.name || sessionUser?.email?.split("@")[0] || "";

  const handleLogout = () => {
    clearSession();
    navigate(routes.login);
  };

  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    let mounted = true;
    const check = async () => {
      try {
        await api.checkReady();
        if (mounted) setSystemReady(true);
      } catch {
        if (mounted) setSystemReady(false);
      }
    };
    check();
    const iv = setInterval(check, 15_000);
    return () => { mounted = false; clearInterval(iv); };
  }, []);

  return (
    <header className="sticky top-0 z-40 border-b border-surface-800/40 bg-[#030712]/90 backdrop-blur-xl">
      <div className="max-w-7xl mx-auto px-3 sm:px-5 lg:px-8">
        <div className="flex items-center justify-between h-14 gap-3 min-w-0">

          {/* ── Brand ───────────────────────────────────────────────── */}
          <NavLink
            to={routes.home}
            className="flex items-center gap-2 shrink-0 group focus:outline-none"
          >
            <OpsMindLogo className="w-8 h-8 shrink-0 group-hover:scale-105 transition-transform" />
            <span className="font-app-heading text-base text-white tracking-tight whitespace-nowrap hidden sm:block">
              OpsMind
            </span>
          </NavLink>

          {/* ── Primary nav (desktop) ────────────────────────────────── */}
          <nav
            className="hidden lg:flex items-center gap-0.5 bg-surface-900/60 border border-surface-700/50 p-1 rounded-xl shrink-0"
            aria-label="Primary"
          >
            <NavLink to={routes.home} end title="Home"
              className={({ isActive }) => navLink(isActive)}>
              <Compass className="w-3.5 h-3.5 shrink-0" />
              Home
            </NavLink>

            <NavLink to={routes.console} title="Console"
              className={({ isActive }) => navLink(isActive)}>
              <Activity className="w-3.5 h-3.5 shrink-0" />
              Console
            </NavLink>

            <NavLink to={routes.history} title="History"
              className={({ isActive }) => navLink(isActive)}>
              {({ isActive }) => (
                <>
                  <History className="w-3.5 h-3.5 shrink-0" />
                  History
                  <NavCount count={investigationCount} active={isActive} />
                </>
              )}
            </NavLink>

            <NavLink to={routes.cases} title="Cases"
              className={({ isActive }) => navLink(isActive)}>
              {({ isActive }) => (
                <>
                  <Brain className="w-3.5 h-3.5 shrink-0" />
                  Cases
                  <NavCount count={approvedCount} active={isActive} />
                </>
              )}
            </NavLink>

            <NavLink to={routes.settings} title="Settings"
              className={({ isActive }) => navLink(isActive)}>
              <Settings2 className="w-3.5 h-3.5 shrink-0" />
              Settings
            </NavLink>
          </nav>

          {/* ── Right-side actions ───────────────────────────────────── */}
          <div className="flex items-center gap-1.5 shrink-0">

            {/* API status dot */}
            <ApiDot ready={systemReady} />

            {/* Notification bell */}
            {hasJwt && <NotificationBell />}

            {/* User / sign-in */}
            {hasJwt ? (
              <div className="hidden lg:flex items-center gap-1.5 pl-1.5 border-l border-surface-800 ml-0.5">
                <div className="flex items-center gap-2 px-2 py-1 rounded-lg bg-surface-900/60 border border-surface-800/80 max-w-[10rem]">
                  <UserAvatar name={displayName} />
                  <span className="text-xs text-surface-300 truncate hidden xl:block">
                    {displayName}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={handleLogout}
                  title="Sign out"
                  className="p-2 rounded-lg text-surface-500 hover:text-rose-400 hover:bg-rose-950/30 transition-colors"
                >
                  <LogOut className="w-3.5 h-3.5" />
                </button>
              </div>
            ) : (
              <Button
                variant="secondary"
                size="sm"
                icon={<LogIn className="w-3.5 h-3.5" />}
                onClick={() => navigate(routes.login)}
                className="hidden lg:flex"
              >
                Sign in
              </Button>
            )}

            {/* New Investigation CTA */}
            <Button
              variant="accent"
              size="sm"
              icon={<PlusCircle className="w-4 h-4" />}
              onClick={onNewInvestigationClick}
              className="px-3 sm:px-3.5"
            >
              <span className="hidden sm:inline">New Investigation</span>
              <span className="sm:hidden font-semibold">New</span>
            </Button>

            {/* Mobile menu toggle */}
            <button
              type="button"
              onClick={() => setIsMobileMenuOpen((v) => !v)}
              className="lg:hidden p-2 rounded-lg bg-surface-900/80 border border-surface-700 text-surface-300 hover:text-white transition-colors"
              aria-label="Toggle menu"
            >
              {isMobileMenuOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
            </button>
          </div>
        </div>

        {/* ── Mobile menu ──────────────────────────────────────────────── */}
        {isMobileMenuOpen && (
          <div className="lg:hidden py-3 border-t border-surface-800/60 space-y-1 animate-slide-up pb-[max(0.75rem,env(safe-area-inset-bottom))]">

            {/* API + user row */}
            <div className="flex items-center justify-between px-3 py-2 mb-1 rounded-lg bg-surface-900/40 border border-surface-800/60">
              <div className="flex items-center gap-2 text-xs text-surface-400">
                <ApiDot ready={systemReady} />
                {systemReady === true ? "API Ready" : systemReady === false ? "API Offline" : "Checking…"}
              </div>
              {hasJwt && sessionUser && (
                <div className="flex items-center gap-1.5">
                  <UserAvatar name={displayName} />
                  <span className="text-xs text-surface-300 max-w-[8rem] truncate">{displayName}</span>
                </div>
              )}
            </div>

            {/* Nav links */}
            <NavLink to={routes.home} end className={({ isActive }) => mobileNavLink(isActive)}>
              <span className="flex items-center gap-2.5"><Compass className="w-4 h-4" /> Home</span>
            </NavLink>

            <NavLink to={routes.console} className={({ isActive }) => mobileNavLink(isActive)}>
              <span className="flex items-center gap-2.5"><Activity className="w-4 h-4" /> Console</span>
            </NavLink>

            <NavLink to={routes.history} className={({ isActive }) => mobileNavLink(isActive)}>
              <span className="flex items-center gap-2.5"><History className="w-4 h-4" /> History</span>
              {investigationCount > 0 && (
                <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-surface-800 text-surface-300">{investigationCount}</span>
              )}
            </NavLink>

            <NavLink to={routes.cases} className={({ isActive }) => mobileNavLink(isActive)}>
              <span className="flex items-center gap-2.5"><Brain className="w-4 h-4" /> Case Memory</span>
              {approvedCount > 0 && (
                <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-accent-950 text-accent-300 border border-accent-800/60">{approvedCount}</span>
              )}
            </NavLink>

            <NavLink to={routes.settings} className={({ isActive }) => mobileNavLink(isActive)}>
              <span className="flex items-center gap-2.5"><Settings2 className="w-4 h-4" /> Settings</span>
            </NavLink>

            {/* Auth action */}
            {hasJwt ? (
              <button
                type="button"
                onClick={handleLogout}
                className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium text-rose-400 hover:bg-rose-950/30 transition-colors mt-1"
              >
                <LogOut className="w-4 h-4" /> Sign out
              </button>
            ) : (
              <NavLink to={routes.login} className={({ isActive }) => mobileNavLink(isActive)}>
                <span className="flex items-center gap-2.5"><LogIn className="w-4 h-4" /> Sign in</span>
              </NavLink>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
