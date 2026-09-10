import { Navigate, Route, Routes } from "react-router-dom";
import { RequireAuth } from "./components/auth/RequireAuth";
import { AppShell } from "./layouts/AppShell";
import { LandingPageRoute } from "./pages/LandingPageRoute";
import { ConsolePage } from "./pages/ConsolePage";
import { HistoryPage } from "./pages/HistoryPage";
import { CasesPage } from "./pages/CasesPage";
import { LoginPage } from "./pages/LoginPage";
import { SignupPage } from "./pages/SignupPage";
import { JoinPage } from "./pages/JoinPage";
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";
import { ResetPasswordPage } from "./pages/ResetPasswordPage";
import { SettingsPage } from "./pages/SettingsPage";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPageRoute />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/join" element={<JoinPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />

      <Route
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route path="/console" element={<ConsolePage />} />
        <Route path="/console/:investigationId" element={<ConsolePage />} />
        <Route path="/console/:investigationId/:subView" element={<ConsolePage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/cases" element={<CasesPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
