import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { LandingPage } from "../components/landing/LandingPage";
import { api } from "../lib/api";
import { routes } from "../lib/routes";

export function LandingPageRoute() {
  const navigate = useNavigate();
  const [investigationCount, setInvestigationCount] = useState(0);
  const [approvedCount, setApprovedCount] = useState(0);

  useEffect(() => {
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

  return (
    <div className="min-h-screen bg-surface-950 text-surface-100 flex flex-col font-sans selection:bg-brand-500 selection:text-white">
      <main className="flex-1 w-full">
        <LandingPage
          onLaunchConsole={() => navigate(routes.console)}
          onSelectScenario={(question) =>
            navigate(routes.console, { state: { launchQuestion: question } })
          }
          onExploreHistory={() => navigate(routes.history)}
          onExploreCases={() => navigate(routes.cases)}
          onExploreTools={() => navigate(routes.tools)}
          investigationCount={investigationCount}
          approvedCount={approvedCount}
        />
      </main>
    </div>
  );
}
