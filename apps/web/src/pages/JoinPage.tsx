import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { CheckCircle2, Clock, Loader2, XCircle } from "lucide-react";
import { AuthLayout } from "../layouts/AuthLayout";
import { Button } from "../components/common/Button";
import { api, setAccessToken, setStoredUser } from "../lib/api";
import { routes } from "../lib/routes";

type JoinState =
  | { phase: "form" }
  // password kept in memory so we can auto-login when approved
  | { phase: "pending"; email: string; password: string; invite_code: string; request_id: string }
  | { phase: "signing_in" }
  | { phase: "approved" }
  | { phase: "rejected"; reason: string | null };

const POLL_INTERVAL_MS = 10_000;

export function JoinPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [inviteCode, setInviteCode] = useState(params.get("code") || "");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [state, setState] = useState<JoinState>({ phase: "form" });
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Kick off polling when we enter the pending phase
  useEffect(() => {
    if (state.phase !== "pending") {
      if (pollRef.current) clearInterval(pollRef.current);
      return;
    }

    const { email: pendingEmail, invite_code, password: pendingPassword } = state;

    const poll = async () => {
      try {
        const res = await api.checkRequestStatus(pendingEmail, invite_code);
        if (res.status === "approved") {
          if (pollRef.current) clearInterval(pollRef.current);
          // Auto-login with the credentials the user already provided
          setState({ phase: "signing_in" });
          try {
            const authRes = await api.login({ email: pendingEmail, password: pendingPassword });
            // Persist JWT + user profile exactly as LoginPage does
            setAccessToken(authRes.access_token);
            setStoredUser(authRes.user);
            setState({ phase: "approved" });
            // Brief success flash then go straight to console
            setTimeout(() => navigate(routes.console, { replace: true }), 1200);
          } catch {
            // Auto-login failed (edge case: password changed or network blip)
            // Fall back to login page with a clear success notice
            setState({ phase: "approved" });
            setTimeout(() => navigate(routes.login + "?notice=access_approved", { replace: true }), 1200);
          }
        } else if (res.status === "rejected") {
          if (pollRef.current) clearInterval(pollRef.current);
          setState({ phase: "rejected", reason: res.rejection_reason ?? null });
        }
      } catch {
        // Silently swallow transient polling errors — UI stays in pending
      }
    };

    // Poll immediately, then on interval
    void poll();
    pollRef.current = setInterval(() => void poll(), POLL_INTERVAL_MS);

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [state, navigate]);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await api.joinInvite({
        invite_code: inviteCode,
        email,
        password,
      });
      // Store password in pending state so we can auto-login after approval
      setState({ phase: "pending", email, password, invite_code: inviteCode, request_id: res.request_id });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "";
      const s = msg.toLowerCase();
      setError(
        s.includes("invite") && (s.includes("invalid") || s.includes("not found") || s.includes("expired") || s.includes("revoked"))
          ? "This invite code is invalid or has expired. Ask your admin for a new one."
          : s.includes("invite") && s.includes("used")
          ? "This invite code has reached its usage limit. Ask your admin for a new code."
          : s.includes("email") && s.includes("already")
          ? "This email is already registered in a workspace. Try signing in instead."
          : msg || "Could not submit your access request. Please check the invite code and try again."
      );
    } finally {
      setLoading(false);
    }
  };

  if (state.phase === "signing_in" || state.phase === "approved") {
    return (
      <AuthLayout
        title="Access approved!"
        subtitle="Signing you in to your workspace…"
      >
        <div className="flex flex-col items-center gap-4 py-6 text-center">
          {state.phase === "signing_in" ? (
            <Loader2 className="w-12 h-12 text-accent-400 animate-spin" />
          ) : (
            <CheckCircle2 className="w-12 h-12 text-accent-400" />
          )}
          <p className="text-sm text-surface-300">
            {state.phase === "signing_in" ? "Completing sign-in…" : "Redirecting to console…"}
          </p>
        </div>
      </AuthLayout>
    );
  }

  if (state.phase === "rejected") {
    return (
      <AuthLayout
        title="Access request rejected"
        subtitle="Your request was not approved by the workspace admin."
      >
        <div className="flex flex-col items-center gap-4 py-6 text-center">
          <XCircle className="w-12 h-12 text-rose-400" />
          {state.reason ? (
            <p className="text-sm text-surface-300">
              Reason: <span className="text-surface-100">{state.reason}</span>
            </p>
          ) : (
            <p className="text-sm text-surface-400">No reason was provided by the admin.</p>
          )}
          <p className="text-xs text-surface-500">
            You can try again with a new invite code, or contact your workspace admin.
          </p>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setState({ phase: "form" })}
          >
            Try again
          </Button>
        </div>
      </AuthLayout>
    );
  }

  if (state.phase === "pending") {
    return (
      <AuthLayout
        title="Request submitted"
        subtitle="An admin will review your access request shortly."
      >
        <div className="flex flex-col items-center gap-4 py-6 text-center">
          <Clock className="w-12 h-12 text-accent-400 animate-pulse" />
          <div className="space-y-1">
            <p className="text-sm text-surface-100 font-medium">Waiting for admin approval</p>
            <p className="text-xs text-surface-400">
              This page checks automatically every 10 seconds.
            </p>
            <p className="text-xs text-surface-500 mt-2">
              Submitted as <span className="text-surface-300 font-mono">{state.email}</span>
            </p>
          </div>
          <div className="flex gap-2 pt-2">
            <div className="w-2 h-2 rounded-full bg-accent-400 animate-bounce" style={{ animationDelay: "0ms" }} />
            <div className="w-2 h-2 rounded-full bg-accent-400 animate-bounce" style={{ animationDelay: "150ms" }} />
            <div className="w-2 h-2 rounded-full bg-accent-400 animate-bounce" style={{ animationDelay: "300ms" }} />
          </div>
        </div>
      </AuthLayout>
    );
  }

  // Default: form phase
  return (
    <AuthLayout
      title="Join with invite"
      subtitle="Submit an access request. An admin will review and approve you shortly."
      footer={
        <p>
          Starting a new company?{" "}
          <Link to={routes.signup} className="text-accent-400 hover:text-accent-300">
            Sign up
          </Link>
        </p>
      }
    >
      <form className="space-y-3.5" onSubmit={(e) => void onSubmit(e)}>
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
          <div className="flex items-start gap-2 text-xs text-rose-300 bg-rose-950/50 border border-rose-800/60 rounded-lg px-3 py-2.5">
            <span className="shrink-0 mt-0.5">⚠</span>
            <span>{error}</span>
          </div>
        ) : null}
        <Button type="submit" variant="accent" className="w-full" loading={loading}>
          Request access
        </Button>
      </form>
    </AuthLayout>
  );
}
