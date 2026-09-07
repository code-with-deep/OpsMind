import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { AuthLayout } from "../layouts/AuthLayout";
import { Button } from "../components/common/Button";
import { api } from "../lib/api";
import { routes } from "../lib/routes";

export function JoinPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [inviteCode, setInviteCode] = useState(params.get("code") || "");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await api.joinInvite({
        invite_code: inviteCode,
        email,
        password,
      });
      navigate(routes.console);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not join with invite");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout
      title="Join with invite"
      subtitle="Redeem an invite code to join as Investigator for that company only."
      footer={
        <p>
          Starting a new company?{" "}
          <Link to={routes.signup} className="text-accent-400 hover:text-accent-300">
            Sign up
          </Link>
        </p>
      }
    >
      <form className="space-y-3.5" onSubmit={onSubmit}>
        <label className="block space-y-1.5">
          <span className="text-xs font-medium text-surface-300">Invite code</span>
          <input
            type="text"
            required
            value={inviteCode}
            onChange={(e) => setInviteCode(e.target.value.toUpperCase())}
            placeholder="OM-XXXX-XXXX"
            className="w-full min-h-11 rounded-lg bg-surface-900 border border-surface-700 px-3 font-mono text-base sm:text-sm text-surface-100 focus:outline-none focus:ring-2 focus:ring-accent-500/40"
          />
        </label>
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
          Join company
        </Button>
      </form>
    </AuthLayout>
  );
}
