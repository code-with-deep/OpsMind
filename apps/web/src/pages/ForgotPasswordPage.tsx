import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { AuthLayout } from "../layouts/AuthLayout";
import { Button } from "../components/common/Button";
import { FormAlert, TextField } from "../components/common/FormField";
import { useFormFields } from "../hooks/useFormFields";
import { api, ApiError, errorMessage } from "../lib/api";
import { routes } from "../lib/routes";
import { validateEmail } from "../lib/validation";

export function ForgotPasswordPage() {
  const location = useLocation();
  const prefill = (location.state as { email?: string } | null)?.email || "";
  const form = useFormFields({ email: prefill }, (v) => ({ email: validateEmail(v.email) }));
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setMessage(null);
    const values = form.validateForSubmit();
    if (!values) return;
    setLoading(true);
    try {
      const res = await api.forgotPassword({ email: values.email.trim() });
      setMessage(
        `${res.message || "If an account exists for that email, we sent a password reset link."} ` +
          "Check your inbox and spam folder — the link expires soon."
      );
    } catch (err: unknown) {
      if (!(err instanceof ApiError && form.applyServerErrors(err.fieldErrors))) {
        setError(errorMessage(err, "Couldn't send the reset link. Please try again."));
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout
      title="Forgot password"
      subtitle="Enter your account email and we’ll send you a link to choose a new password."
      footer={
        <p>
          Remembered it?{" "}
          <Link to={routes.login} className="text-accent-400 hover:text-accent-300">
            Sign in
          </Link>
        </p>
      }
    >
      {message ? <FormAlert tone="success">{message}</FormAlert> : null}
      <form className="space-y-3.5" onSubmit={onSubmit} noValidate>
        <TextField
          label="Email"
          type="email"
          inputMode="email"
          autoComplete="email"
          placeholder="name@company.com"
          {...form.bind("email")}
        />
        {error ? <FormAlert>{error}</FormAlert> : null}
        <Button type="submit" variant="accent" className="w-full" loading={loading}>
          {message ? "Send another link" : "Send reset link"}
        </Button>
      </form>
    </AuthLayout>
  );
}
