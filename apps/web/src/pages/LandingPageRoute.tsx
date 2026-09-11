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
  const [demoLoading, setDemoLoading] = useState(false);
  const [demoError, setDemoError] = useState<string | null>(null);
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

  const handleTryDemo = async () => {
    setDemoError(null);
    setDemoLoading(true);
    try {
      await api.demoLogin();
      // Land straight on the scenario picker so visitors can pick a preloaded
      // incident ("Why did revenue decrease...", "Carrier SLA spike", ...) and
      // run it immediately against the seeded demo tenant.
      navigate(routes.console, { state: { openNewModal: true } });
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Could not start the demo. Please try again.";
      setDemoError(message);
    } finally {
      setDemoLoading(false);
    }
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
          onTryDemo={() => void handleTryDemo()}
          demoLoading={demoLoading}
          demoError={demoError}
          investigationCount={investigationCount}
          approvedCount={approvedCount}
        />
      </main>
    </div>
  );
}
