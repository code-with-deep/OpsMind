import { Navigate, useLocation } from "react-router-dom";
import {
  DEMO_BOOTSTRAP_API_KEY,
  canAccessApp,
  clearApiKey,
  getApiKey,
} from "../../lib/api";
import { routes } from "../../lib/routes";

/**
 * Gate app-shell routes. Console/History/Settings require email login (JWT).
 * API-key-only must not open the product UI.
 */
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const location = useLocation();

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

  return <>{children}</>;
}
