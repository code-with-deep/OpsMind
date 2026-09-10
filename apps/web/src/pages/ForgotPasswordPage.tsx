import { useState } from "react";
import { Link } from "react-router-dom";
import { AuthLayout } from "../layouts/AuthLayout";
import { Button } from "../components/common/Button";
import { api } from "../lib/api";
import { routes } from "../lib/routes";

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const res = await api.forgotPassword({ email });
      setMessage(
        res.message ||
          "If an account exists for that email, we sent a password reset link.",
      );
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout
      title="Forgot password"
      subtitle="We’ll email you a link to choose a new password."
      footer={
        <p>
          Remembered it?{" "}
          <Link to={routes.login} className="text-accent-400 hover:text-accent-300">
            Sign in
          </Link>
        </p>
      }
    >
      {message ? (
        <p className="text-xs text-accent-200 bg-accent-950/40 border border-accent-800/50 rounded-lg px-3 py-2">
          {message}
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
        {error ? (
          <p className="text-xs text-rose-300 bg-rose-950/50 border border-rose-800/60 rounded-lg px-3 py-2">
            {error}
          </p>
        ) : null}
        <Button type="submit" variant="accent" className="w-full" loading={loading}>
          Send reset link
        </Button>
      </form>
    </AuthLayout>
  );
}
