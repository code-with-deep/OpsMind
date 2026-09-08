import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { AuthLayout } from "../layouts/AuthLayout";
import { Button } from "../components/common/Button";
import { api, getAccessToken } from "../lib/api";
import { routes } from "../lib/routes";

type LoginLocationState = {
  from?: string;
  launchState?: Record<string, unknown> | null;
  notice?: string;
};

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const navState = (location.state as LoginLocationState | null) || null;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!getAccessToken()) return;
    const next = navState?.from || routes.console;
    navigate(next, {
      replace: true,
      state: navState?.launchState || undefined,
    });
  }, [navigate, navState?.from, navState?.launchState]);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await api.login({ email, password });
      const next = navState?.from || routes.console;
      navigate(next, {
        replace: true,
        state: navState?.launchState || undefined,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "";
      const s = msg.toLowerCase();
      setError(
        s.includes("incorrect") || s.includes("credentials") || s.includes("password") || s.includes("401")
          ? "Incorrect email or password. Please try again."
          : s.includes("not found") || s.includes("no account")
          ? "No account found with that email. Check the address or sign up."
          : msg || "Sign-in failed. Please try again."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout
      title="Sign in"
      subtitle="Access your company’s OpsMind workspace."
      footer={
        <p>
          New company?{" "}
          <Link
            to={routes.signup}
            state={navState}
            className="text-accent-400 hover:text-accent-300"
          >
            Create an account
          </Link>
          {" · "}
          <Link to={routes.join} className="text-accent-400 hover:text-accent-300">
            Join with invite
          </Link>
        </p>
      }
    >
      {navState?.notice ? (
        <p className="text-xs text-accent-200 bg-accent-950/40 border border-accent-800/50 rounded-lg px-3 py-2">
          {navState.notice}
        </p>
      ) : null}
      <form className="space-y-3.5" onSubmit={onSubmit}>
        <label className="block space-y-1.5">
          <span className="text-xs font-medium text-surface-300">Email</span>
          <input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full min-h-11 rounded-lg bg-surface-900 border border-surface-700 px-3 text-base sm:text-sm text-surface-100 focus:outline-none focus:ring-2 focus:ring-accent-500/40"
          />
        </label>
        <label className="block space-y-1.5">
          <span className="text-xs font-medium text-surface-300">Password</span>
          <input
            type="password"
            required
            minLength={8}
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full min-h-11 rounded-lg bg-surface-900 border border-surface-700 px-3 text-base sm:text-sm text-surface-100 focus:outline-none focus:ring-2 focus:ring-accent-500/40"
          />
        </label>
        {error ? (
          <div className="flex items-start gap-2 text-xs text-rose-300 bg-rose-950/50 border border-rose-800/60 rounded-lg px-3 py-2.5">
            <span className="shrink-0 mt-0.5">⚠</span>
            <span>{error}</span>
          </div>
        ) : null}
        <Button type="submit" variant="accent" className="w-full" loading={loading}>
          Sign in
        </Button>
      </form>
    </AuthLayout>
  );
}
