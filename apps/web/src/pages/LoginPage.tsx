import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { AuthLayout } from "../layouts/AuthLayout";
import { Button } from "../components/common/Button";
import { FormAlert, TextField } from "../components/common/FormField";
import { useFormFields } from "../hooks/useFormFields";
import { api, ApiError, errorMessage, getAccessToken } from "../lib/api";
import { routes } from "../lib/routes";
import { validateEmail, validateExistingPassword } from "../lib/validation";

type LoginLocationState = {
  from?: string;
  launchState?: Record<string, unknown> | null;
  notice?: string;
};

const QUERY_NOTICES: Record<string, string> = {
  session_expired: "Your session has expired. Please sign in again.",
  access_approved: "Your access request was approved. You can now sign in.",
};

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const navState = (location.state as LoginLocationState | null) || null;
  // P1-9: hard redirects (e.g. after a 401 clears the session) carry the notice
  // as a query param rather than router state.
  const queryNotice = new URLSearchParams(location.search).get("notice");
  const notice = navState?.notice || (queryNotice ? QUERY_NOTICES[queryNotice] : undefined);
  const form = useFormFields({ email: "", password: "" }, (v) => ({
    email: validateEmail(v.email),
    password: validateExistingPassword(v.password),
  }));
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
    setError(null);
    const values = form.validateForSubmit();
    if (!values) return;
    setLoading(true);
    try {
      await api.login({ email: values.email.trim(), password: values.password });
      const next = navState?.from || routes.console;
      navigate(next, {
        replace: true,
        state: navState?.launchState || undefined,
      });
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 401) {
        setError("Incorrect email or password. Check both and try again.");
      } else if (!(err instanceof ApiError && form.applyServerErrors(err.fieldErrors))) {
        setError(errorMessage(err, "Sign-in failed. Please try again."));
      }
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
      {notice ? <FormAlert tone="info">{notice}</FormAlert> : null}
      <form className="space-y-3.5" onSubmit={onSubmit} noValidate>
        <TextField
          label="Email"
          type="email"
          inputMode="email"
          autoComplete="email"
          placeholder="name@company.com"
          autoFocus
          {...form.bind("email")}
        />
        <TextField
          label="Password"
          type="password"
          autoComplete="current-password"
          {...form.bind("password")}
        />
        <div className="flex justify-end -mt-1">
          <Link
            to={routes.forgotPassword}
            state={{ email: form.values.email.trim() }}
            className="text-xs text-accent-400 hover:text-accent-300"
          >
            Forgot password?
          </Link>
        </div>
        {error ? <FormAlert>{error}</FormAlert> : null}
        <Button type="submit" variant="accent" className="w-full" loading={loading}>
          Sign in
        </Button>
      </form>
    </AuthLayout>
  );
}
