import { useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { AuthLayout } from "../layouts/AuthLayout";
import { Button } from "../components/common/Button";
import { api } from "../lib/api";
import { routes } from "../lib/routes";

export function ResetPasswordPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const token = useMemo(() => (params.get("token") || "").trim(), [params]);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) {
      setError("This reset link is missing a token. Request a new one.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await api.resetPassword({ token, new_password: password });
      navigate(routes.login, {
        replace: true,
        state: { notice: "Password updated. Sign in with your new password." },
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Reset failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout
      title="Reset password"
      subtitle="Choose a new password for your OpsMind account."
      footer={
        <p>
          <Link
            to={routes.forgotPassword}
            className="text-accent-400 hover:text-accent-300"
          >
            Request a new link
          </Link>
          {" · "}
          <Link to={routes.login} className="text-accent-400 hover:text-accent-300">
            Sign in
          </Link>
        </p>
      }
    >
      {!token ? (
        <p className="text-xs text-rose-300 bg-rose-950/50 border border-rose-800/60 rounded-lg px-3 py-2">
          Missing or invalid reset link. Request a new password reset email.
        </p>
      ) : null}
      <form className="space-y-3.5" onSubmit={onSubmit}>
        <label className="block space-y-1.5">
          <span className="text-xs font-medium text-surface-300">New password</span>
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
        <label className="block space-y-1.5">
          <span className="text-xs font-medium text-surface-300">Confirm password</span>
          <input
            type="password"
            required
            minLength={8}
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            className="w-full min-h-11 rounded-lg bg-surface-900 border border-surface-700 px-3 text-base sm:text-sm text-surface-100 focus:outline-none focus:ring-2 focus:ring-accent-500/40"
          />
        </label>
        {error ? (
          <p className="text-xs text-rose-300 bg-rose-950/50 border border-rose-800/60 rounded-lg px-3 py-2">
            {error}
          </p>
        ) : null}
        <Button
          type="submit"
          variant="accent"
          className="w-full"
          loading={loading}
          disabled={!token}
        >
          Update password
        </Button>
      </form>
    </AuthLayout>
  );
}
