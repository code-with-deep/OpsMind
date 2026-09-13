import { forwardRef, InputHTMLAttributes, ReactNode, useId, useState } from "react";
import { AlertCircle, CheckCircle2, Circle, Eye, EyeOff } from "lucide-react";
import { passwordRules } from "../../lib/validation";

interface TextFieldProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, "onChange" | "value"> {
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  hint?: ReactNode;
}

/** Labelled input with inline error, optional hint and a show/hide toggle for passwords. */
export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(function TextField(
  { label, value, onChange, error, hint, type = "text", id, className = "", ...rest },
  ref
) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const messageId = `${inputId}-message`;
  const [revealed, setRevealed] = useState(false);
  const isPassword = type === "password";

  return (
    <div className="space-y-1.5">
      <label htmlFor={inputId} className="block text-xs font-medium text-surface-300">
        {label}
      </label>
      <div className="relative">
        <input
          ref={ref}
          id={inputId}
          type={isPassword && revealed ? "text" : type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          aria-invalid={error ? true : undefined}
          aria-describedby={error || hint ? messageId : undefined}
          className={`w-full min-h-11 rounded-lg bg-surface-900 border px-3 text-base sm:text-sm text-surface-100 placeholder:text-surface-500 focus:outline-none focus:ring-2 transition-colors ${
            error
              ? "border-rose-600/80 focus:ring-rose-500/40"
              : "border-surface-700 focus:ring-accent-500/40"
          } ${isPassword ? "pr-11" : ""} ${className}`}
          {...rest}
        />
        {isPassword ? (
          <button
            type="button"
            onClick={() => setRevealed((v) => !v)}
            aria-label={revealed ? "Hide password" : "Show password"}
            aria-pressed={revealed}
            className="absolute inset-y-0 right-0 flex items-center px-3 text-surface-400 hover:text-surface-200 focus:outline-none focus-visible:text-accent-300"
          >
            {revealed ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        ) : null}
      </div>
      {error ? (
        <p id={messageId} role="alert" className="flex items-start gap-1.5 text-xs text-rose-300">
          <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-px" />
          <span>{error}</span>
        </p>
      ) : hint ? (
        <p id={messageId} className="text-xs text-surface-500">
          {hint}
        </p>
      ) : null}
    </div>
  );
});

/** Live checklist of the password rules, shown while choosing a password. */
export function PasswordChecklist({ password }: { password: string }) {
  if (!password) return null;
  return (
    <ul className="grid grid-cols-1 xs:grid-cols-2 gap-x-3 gap-y-1 -mt-1" aria-label="Password requirements">
      {passwordRules(password).map((rule) => (
        <li
          key={rule.id}
          className={`flex items-center gap-1.5 text-[11px] ${rule.met ? "text-accent-300" : "text-surface-500"}`}
        >
          {rule.met ? <CheckCircle2 className="w-3 h-3 shrink-0" /> : <Circle className="w-3 h-3 shrink-0" />}
          <span>
            {rule.label}
            <span className="sr-only">{rule.met ? " (met)" : " (not met)"}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}

/** Form-level message (errors that don't belong to one field, or success notices). */
export function FormAlert({ tone = "error", children }: { tone?: "error" | "success" | "info"; children: ReactNode }) {
  const styles = {
    error: "text-rose-200 bg-rose-950/50 border-rose-800/60",
    success: "text-emerald-200 bg-emerald-950/40 border-emerald-800/50",
    info: "text-accent-200 bg-accent-950/40 border-accent-800/50",
  }[tone];
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={`flex items-start gap-2 text-xs border rounded-lg px-3 py-2.5 leading-relaxed ${styles}`}
    >
      {tone === "error" ? (
        <AlertCircle className="w-4 h-4 shrink-0" />
      ) : (
        <CheckCircle2 className="w-4 h-4 shrink-0" />
      )}
      <span>{children}</span>
    </div>
  );
}
