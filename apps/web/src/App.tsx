import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./layouts/AppShell";
import { LandingPageRoute } from "./pages/LandingPageRoute";
import { ConsolePage } from "./pages/ConsolePage";
import { HistoryPage } from "./pages/HistoryPage";
import { CasesPage } from "./pages/CasesPage";
import { ToolsPage } from "./pages/ToolsPage";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPageRoute />} />

      <Route element={<AppShell />}>
        <Route path="/console" element={<ConsolePage />} />
        <Route path="/console/:investigationId" element={<ConsolePage />} />
        <Route path="/console/:investigationId/:subView" element={<ConsolePage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/cases" element={<CasesPage />} />
        <Route path="/tools" element={<ToolsPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
