import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { AuthLayout } from "../layouts/AuthLayout";
import { Button } from "../components/common/Button";
import { FormAlert, PasswordChecklist, TextField } from "../components/common/FormField";
import { useFormFields } from "../hooks/useFormFields";
import { api, ApiError, errorMessage, getAccessToken } from "../lib/api";
import { routes } from "../lib/routes";
import {
  validateCompanyName,
  validateConfirmPassword,
  validateEmail,
  validateNewPassword,
} from "../lib/validation";

type AuthNavState = {
  from?: string;
  launchState?: Record<string, unknown> | null;
};

export function SignupPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const navState = (location.state as AuthNavState | null) || null;
  const form = useFormFields(
    { company_name: "", email: "", password: "", confirm_password: "" },
    (v) => ({
      company_name: validateCompanyName(v.company_name),
      email: validateEmail(v.email),
      password: validateNewPassword(v.password),
      confirm_password: validateConfirmPassword(v.password, v.confirm_password),
    })
  );
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
    if (!form.validateForSubmit()) return;
    setLoading(true);
    try {
      await api.signup({
        company_name: form.values.company_name.trim(),
        email: form.values.email.trim(),
        password: form.values.password,
      });
      const next = navState?.from || routes.console;
      navigate(next, {
        replace: true,
        state: navState?.launchState || undefined,
      });
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 409) {
        form.applyServerErrors({ email: err.message });
      } else if (!(err instanceof ApiError && form.applyServerErrors(err.fieldErrors))) {
        setError(errorMessage(err, "Could not create your workspace. Please try again."));
      }
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
          {" · "}
          <Link to={routes.forgotPassword} className="text-accent-400 hover:text-accent-300">
            Forgot password?
          </Link>
        </p>
      }
    >
      <form className="space-y-3.5" onSubmit={onSubmit} noValidate>
        <TextField
          label="Company name"
          autoComplete="organization"
          placeholder="Acme Retail"
          autoFocus
          maxLength={120}
          {...form.bind("company_name")}
        />
        <TextField
          label="Work email"
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
          Create workspace
        </Button>
      </form>
    </AuthLayout>
  );
}
