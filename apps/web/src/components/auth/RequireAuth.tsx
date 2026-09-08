import { useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { ShieldOff } from "lucide-react";
import {
  api,
  DEMO_BOOTSTRAP_API_KEY,
  canAccessApp,
  clearApiKey,
  clearSession,
  getApiKey,
} from "../../lib/api";
import { routes } from "../../lib/routes";

/**
 * Gate app-shell routes. Console/History/Settings require email login (JWT).
 * API-key-only must not open the product UI.
 * If the backend returns 403 "revoked", show a dedicated revoked screen.
 */
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const [revokedError, setRevokedError] = useState(false);

  useEffect(() => {
    // We listen for the specific 403 revoked error from the API layer.
    // When /auth/me or any protected call returns "Account access has been revoked.",
    // the error surfaces here. We detect it by watching storage events + errors.
    // The simplest approach: check /auth/me on mount and on focus.
    const checkMe = async () => {
      if (!canAccessApp()) return;
      try {
        await api.me();
        setRevokedError(false);
      } catch (err: unknown) {
        if (err instanceof Error && err.message.toLowerCase().includes("revoked")) {
          setRevokedError(true);
        }
      }
    };

    void checkMe();
    const onFocus = () => void checkMe();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, []);

  if (!canAccessApp()) {
    // Stale demo key made Console look "open" while header showed Sign in.
    if (getApiKey() === DEMO_BOOTSTRAP_API_KEY) {
      clearApiKey();
    }
    return (
      <Navigate
        to={routes.login}
        replace
        state={{
          from: location.pathname + location.search,
          notice:
            "Sign in with your company account to open the console. An API key alone is not enough.",
        }}
      />
    );
  }

  if (revokedError) {
    return (
      <div className="min-h-screen bg-[#030712] flex items-center justify-center p-4">
        <div className="max-w-md w-full app-panel rounded-2xl p-8 text-center space-y-5">
          <ShieldOff className="w-12 h-12 text-rose-400 mx-auto" />
          <div className="space-y-2">
            <h1 className="font-app-heading text-xl text-white">Access revoked</h1>
            <p className="text-sm text-surface-400">
              Your access to this workspace has been revoked by an administrator.
            </p>
            <p className="text-xs text-surface-500">
              If you believe this is a mistake, please contact your workspace admin.
            </p>
          </div>
          <button
            type="button"
            onClick={() => {
              clearSession();
              window.location.href = routes.login;
            }}
            className="w-full py-2.5 rounded-xl bg-surface-800 border border-surface-700 text-sm text-surface-100 hover:bg-surface-700 transition-colors"
          >
            Sign out
          </button>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
