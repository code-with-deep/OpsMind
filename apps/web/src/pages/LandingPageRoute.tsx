import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { LandingPage } from "../components/landing/LandingPage";
import { api, canAccessApp } from "../lib/api";
import { routes } from "../lib/routes";

type AppNavState = Record<string, unknown> | null;

export function LandingPageRoute() {
  const navigate = useNavigate();
  const [investigationCount, setInvestigationCount] = useState(0);
  const [approvedCount, setApprovedCount] = useState(0);
  const authenticated = canAccessApp();

  useEffect(() => {
    if (!canAccessApp()) return;
    void (async () => {
      try {
        const res = await api.listInvestigations();
        setInvestigationCount(res.count);
        setApprovedCount(res.investigations.filter((item) => item.is_approved).length);
      } catch {
        // Landing page works without API connectivity.
      }
    })();
  }, []);

  const goAuthenticated = (path: string, state?: AppNavState) => {
    if (canAccessApp()) {
      navigate(path, state ? { state } : undefined);
      return;
    }
    navigate(routes.login, {
      state: {
        from: path,
        launchState: state || null,
        notice: "Sign in to open the console, or create a workspace to get started.",
      },
    });
  };

  return (
    <div className="min-h-screen bg-surface-950 text-surface-100 flex flex-col font-sans selection:bg-brand-500 selection:text-white">
      <main className="flex-1 w-full">
        <LandingPage
          isAuthenticated={authenticated}
          onGetStarted={() =>
            authenticated ? navigate(routes.console) : navigate(routes.signup)
          }
          onSignIn={() =>
            authenticated ? navigate(routes.console) : navigate(routes.login)
          }
          onLaunchConsole={() => goAuthenticated(routes.console)}
          onExploreHistory={() => goAuthenticated(routes.history)}
          onExploreCases={() => goAuthenticated(routes.cases)}
          investigationCount={investigationCount}
          approvedCount={approvedCount}
        />
      </main>
    </div>
  );
}
