import { useNavigate, useOutletContext } from "react-router-dom";
import { InvestigationList } from "../components/history/InvestigationList";
import { AppShellOutletContext } from "../layouts/AppShell";
import { routes } from "../lib/routes";

export function HistoryPage() {
  const navigate = useNavigate();
  const { investigations, loadDetail, openNewInvestigationModal } =
    useOutletContext<AppShellOutletContext>();

  return (
    <div className="animate-fadeIn">
      <InvestigationList
        investigations={investigations}
        onSelectInvestigation={(id) => {
          void loadDetail(id);
          navigate(routes.consoleInvestigation(id));
        }}
        onNewClick={openNewInvestigationModal}
      />
    </div>
  );
}
