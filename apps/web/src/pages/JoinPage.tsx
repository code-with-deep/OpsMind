import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { CheckCircle2, Clock, Loader2, XCircle } from "lucide-react";
import { AuthLayout } from "../layouts/AuthLayout";
import { Button } from "../components/common/Button";
import { FormAlert, PasswordChecklist, TextField } from "../components/common/FormField";
import { useFormFields } from "../hooks/useFormFields";
import { api, ApiError, errorMessage } from "../lib/api";
import { routes } from "../lib/routes";
import {
  validateConfirmPassword,
  validateEmail,
  validateInviteCode,
  validateNewPassword,
} from "../lib/validation";

type JoinState =
  | { phase: "form" }
  // password kept in memory so we can auto-login when approved
  | { phase: "pending"; email: string; password: string; invite_code: string; request_id: string }
  | { phase: "signing_in" }
  | { phase: "approved" }
  | { phase: "rejected"; reason: string | null };

// This page is public (no session), so it can't use the authenticated live
// stream — it checks the request status on a short interval instead.
const POLL_INTERVAL_MS = 5_000;

export function JoinPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const form = useFormFields(
    {
      invite_code: (params.get("code") || "").toUpperCase(),
      email: "",
      password: "",
      confirm_password: "",
    },
    (v) => ({
      invite_code: validateInviteCode(v.invite_code),
      email: validateEmail(v.email),
      password: validateNewPassword(v.password),
      confirm_password: validateConfirmPassword(v.password, v.confirm_password),
    })
  );
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
            await api.login({ email: pendingEmail, password: pendingPassword });
            setState({ phase: "approved" });
            setTimeout(() => navigate(routes.console, { replace: true }), 1200);
          } catch {
            // Auto-login failed (password changed or network blip) — fall back
            // to the login page with a clear success notice.
            setState({ phase: "approved" });
            setTimeout(() => navigate(routes.login + "?notice=access_approved", { replace: true }), 1200);
          }
        } else if (res.status === "rejected") {
          if (pollRef.current) clearInterval(pollRef.current);
          setState({ phase: "rejected", reason: res.rejection_reason ?? null });
        }
      } catch {
        // Transient polling errors — stay pending and retry on the next tick.
      }
    };

    void poll();
    pollRef.current = setInterval(() => void poll(), POLL_INTERVAL_MS);

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [state, navigate]);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!form.validateForSubmit()) return;
    setLoading(true);
    const { invite_code, email, password } = form.values;
    try {
      const res = await api.joinInvite({ invite_code: invite_code.trim(), email: email.trim(), password });
      setState({
        phase: "pending",
        email: email.trim(),
        password,
        invite_code: invite_code.trim(),
        request_id: res.request_id,
      });
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 409) {
        form.applyServerErrors({ email: err.message });
      } else if (err instanceof ApiError && err.status === 400 && /invite/i.test(err.message)) {
        form.applyServerErrors({ invite_code: err.message });
      } else if (!(err instanceof ApiError && form.applyServerErrors(err.fieldErrors))) {
        setError(errorMessage(err, "Could not submit your access request. Please try again."));
      }
    } finally {
      setLoading(false);
    }
  };

  if (state.phase === "signing_in" || state.phase === "approved") {
    return (
      <AuthLayout title="Access approved!" subtitle="Signing you in to your workspace…">
        <div className="flex flex-col items-center gap-4 py-6 text-center">
          {state.phase === "signing_in" ? (
            <Loader2 className="w-12 h-12 text-accent-400 animate-spin" />
          ) : (
            <CheckCircle2 className="w-12 h-12 text-accent-400" />
          )}
          <p className="text-sm text-surface-300" role="status">
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
          <Button variant="secondary" size="sm" onClick={() => setState({ phase: "form" })}>
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
        <div className="flex flex-col items-center gap-4 py-6 text-center" role="status">
          <Clock className="w-12 h-12 text-accent-400 animate-pulse" />
          <div className="space-y-1">
            <p className="text-sm text-surface-100 font-medium">Waiting for admin approval</p>
            <p className="text-xs text-surface-400">
              Keep this page open — you'll be signed in automatically once approved.
            </p>
            <p className="text-xs text-surface-500 mt-2">
              Submitted as <span className="text-surface-300 font-mono">{state.email}</span>
            </p>
          </div>
          <div className="flex gap-2 pt-2" aria-hidden="true">
            <div className="w-2 h-2 rounded-full bg-accent-400 animate-bounce" style={{ animationDelay: "0ms" }} />
            <div className="w-2 h-2 rounded-full bg-accent-400 animate-bounce" style={{ animationDelay: "150ms" }} />
            <div className="w-2 h-2 rounded-full bg-accent-400 animate-bounce" style={{ animationDelay: "300ms" }} />
          </div>
        </div>
      </AuthLayout>
    );
  }

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
          {" · "}
          <Link to={routes.login} className="text-accent-400 hover:text-accent-300">
            Sign in
          </Link>
        </p>
      }
    >
      <form className="space-y-3.5" onSubmit={(e) => void onSubmit(e)} noValidate>
        <TextField
          label="Invite code"
          placeholder="OM-XXXX-XXXX"
          autoComplete="off"
          spellCheck={false}
          className="font-mono uppercase"
          hint="Paste the code exactly as your admin shared it."
          {...form.bind("invite_code")}
          onChange={(value) => form.setValue("invite_code", value.toUpperCase())}
        />
        <TextField
          label="Email"
          type="email"
          inputMode="email"
          autoComplete="email"
          placeholder="name@company.com"
          {...form.bind("email")}
        />
        <div className="space-y-2.5">
          <TextField
            label="Password"
            type="password"
            autoComplete="new-password"
            {...form.bind("password")}
          />
          <PasswordChecklist password={form.values.password} />
        </div>
        <TextField
          label="Confirm password"
          type="password"
          autoComplete="new-password"
          {...form.bind("confirm_password")}
        />
        {error ? <FormAlert>{error}</FormAlert> : null}
        <Button type="submit" variant="accent" className="w-full" loading={loading}>
          Request access
        </Button>
      </form>
    </AuthLayout>
  );
}
