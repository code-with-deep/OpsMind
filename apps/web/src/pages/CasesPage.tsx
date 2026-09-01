import { useNavigate, useOutletContext } from "react-router-dom";
import { CaseMemoryCatalog } from "../components/cases/CaseMemoryCatalog";
import { AppShellOutletContext } from "../layouts/AppShell";
import { routes } from "../lib/routes";

export function CasesPage() {
  const navigate = useNavigate();
  const { loadDetail } = useOutletContext<AppShellOutletContext>();

  return (
    <div className="animate-fadeIn">
      <CaseMemoryCatalog
        onSelectInvestigation={(id) => {
          void loadDetail(id);
          navigate(routes.consoleInvestigation(id));
        }}
      />
    </div>
  );
}
