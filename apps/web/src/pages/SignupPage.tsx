import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { AuthLayout } from "../layouts/AuthLayout";
import { Button } from "../components/common/Button";
import { api, getAccessToken } from "../lib/api";
import { routes } from "../lib/routes";

type AuthNavState = {
  from?: string;
  launchState?: Record<string, unknown> | null;
};

export function SignupPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const navState = (location.state as AuthNavState | null) || null;
  const [companyName, setCompanyName] = useState("");
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
      await api.signup({
        company_name: companyName,
        email,
        password,
      });
      const next = navState?.from || routes.console;
      navigate(next, {
        replace: true,
        state: navState?.launchState || undefined,
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Signup failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout
      title="Create your workspace"
      subtitle="You become Admin for your company. Invite teammates next."
      footer={
        <p>
          Already have an account?{" "}
          <Link
            to={routes.login}
            state={navState}
            className="text-accent-400 hover:text-accent-300"
          >
            Sign in
          </Link>
        </p>
      }
    >
      <form className="space-y-3.5" onSubmit={onSubmit}>
        <label className="block space-y-1.5">
          <span className="text-xs font-medium text-surface-300">Company name</span>
          <input
            type="text"
            required
            minLength={2}
            value={companyName}
            onChange={(e) => setCompanyName(e.target.value)}
            className="w-full min-h-11 rounded-lg bg-surface-900 border border-surface-700 px-3 text-base sm:text-sm text-surface-100 focus:outline-none focus:ring-2 focus:ring-accent-500/40"
          />
        </label>
        <label className="block space-y-1.5">
          <span className="text-xs font-medium text-surface-300">Work email</span>
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
          <span className="text-xs font-medium text-surface-300">Password (min 8)</span>
          <input
            type="password"
            required
            minLength={8}
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full min-h-11 rounded-lg bg-surface-900 border border-surface-700 px-3 text-base sm:text-sm text-surface-100 focus:outline-none focus:ring-2 focus:ring-accent-500/40"
          />
        </label>
        {error ? (
          <p className="text-xs text-rose-300 bg-rose-950/50 border border-rose-800/60 rounded-lg px-3 py-2">
            {error}
          </p>
        ) : null}
        <Button type="submit" variant="accent" className="w-full" loading={loading}>
          Create workspace
        </Button>
      </form>
    </AuthLayout>
  );
}
