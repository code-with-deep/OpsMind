import { useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { AuthLayout } from "../layouts/AuthLayout";
import { Button } from "../components/common/Button";
import { FormAlert, PasswordChecklist, TextField } from "../components/common/FormField";
import { useFormFields } from "../hooks/useFormFields";
import { api, ApiError, errorMessage } from "../lib/api";
import { routes } from "../lib/routes";
import { validateConfirmPassword, validateNewPassword } from "../lib/validation";

export function ResetPasswordPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const token = useMemo(() => (params.get("token") || "").trim(), [params]);
  const form = useFormFields({ new_password: "", confirm_password: "" }, (v) => ({
    new_password: validateNewPassword(v.new_password, "New password"),
    confirm_password: validateConfirmPassword(v.new_password, v.confirm_password),
  }));
  const [error, setError] = useState<string | null>(null);
  const [linkInvalid, setLinkInvalid] = useState(!token);
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const values = form.validateForSubmit();
    if (!values) return;
    setLoading(true);
    try {
      await api.resetPassword({ token, new_password: values.new_password });
      navigate(routes.login, {
        replace: true,
        state: { notice: "Password updated. Sign in with your new password." },
      });
    } catch (err: unknown) {
      if (err instanceof ApiError && (err.status === 400 || err.fieldErrors.token)) {
        setLinkInvalid(true);
      } else if (!(err instanceof ApiError && form.applyServerErrors(err.fieldErrors))) {
        setError(errorMessage(err, "Couldn't update your password. Please try again."));
      }
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
          <Link to={routes.forgotPassword} className="text-accent-400 hover:text-accent-300">
            Request a new link
          </Link>
          {" · "}
          <Link to={routes.login} className="text-accent-400 hover:text-accent-300">
            Sign in
          </Link>
        </p>
      }
    >
      {linkInvalid ? (
        <FormAlert>
          This reset link is invalid, already used, or expired.{" "}
          <Link to={routes.forgotPassword} className="underline underline-offset-2 hover:text-white">
            Request a new link
          </Link>
          .
        </FormAlert>
      ) : null}
      <form className="space-y-3.5" onSubmit={onSubmit} noValidate>
        <div className="space-y-2.5">
          <TextField
            label="New password"
            type="password"
            autoComplete="new-password"
            disabled={linkInvalid}
            {...form.bind("new_password")}
          />
          <PasswordChecklist password={form.values.new_password} />
        </div>
        <TextField
          label="Confirm new password"
          type="password"
          autoComplete="new-password"
          disabled={linkInvalid}
          {...form.bind("confirm_password")}
        />
        {error ? <FormAlert>{error}</FormAlert> : null}
        <Button
          type="submit"
          variant="accent"
          className="w-full"
          loading={loading}
          disabled={linkInvalid}
        >
          Update password
        </Button>
      </form>
    </AuthLayout>
  );
}
