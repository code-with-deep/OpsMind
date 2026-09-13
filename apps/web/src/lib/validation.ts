/**
 * Client-side form validation. Rules mirror the API (see
 * packages/opsmind/auth/passwords.py and apps/api/app/routes/auth.py) so users
 * see the same messages before and after submitting — keep them in sync.
 */

export const PASSWORD_MIN_LENGTH = 8;
export const PASSWORD_MAX_LENGTH = 128;

// Deliberately permissive: the server's email validator is authoritative.
const EMAIL_PATTERN = /^[^\s@]+@[^\s@.]+(\.[^\s@.]+)+$/;

export type PasswordRule = { id: string; label: string; met: boolean };

export function passwordRules(password: string): PasswordRule[] {
  return [
    {
      id: "length",
      label: `At least ${PASSWORD_MIN_LENGTH} characters`,
      met: password.length >= PASSWORD_MIN_LENGTH && password.length <= PASSWORD_MAX_LENGTH,
    },
    { id: "letter", label: "At least one letter", met: /\p{L}/u.test(password) },
    { id: "number", label: "At least one number", met: /\p{N}/u.test(password) },
    {
      id: "spaces",
      label: "No spaces at the start or end",
      met: password.length > 0 && password.trim() === password,
    },
  ];
}

export function validateEmail(value: string): string | undefined {
  const email = value.trim();
  if (!email) return "Email is required.";
  if (!EMAIL_PATTERN.test(email)) return "Please enter a valid email address, like name@company.com.";
  if (email.length > 254) return "Email must be at most 254 characters.";
  return undefined;
}

/** For a password being checked (sign in, current password) — presence only. */
export function validateExistingPassword(value: string, label = "Password"): string | undefined {
  return value ? undefined : `${label} is required.`;
}

/** For a password being chosen — same policy as the API. */
export function validateNewPassword(value: string, label = "Password"): string | undefined {
  if (!value) return `${label} is required.`;
  if (value.length < PASSWORD_MIN_LENGTH) return `${label} must be at least ${PASSWORD_MIN_LENGTH} characters.`;
  if (value.length > PASSWORD_MAX_LENGTH) return `${label} must be at most ${PASSWORD_MAX_LENGTH} characters.`;
  if (value.trim() !== value) return `${label} can't start or end with a space.`;
  if (!/\p{L}/u.test(value)) return `${label} must include at least one letter.`;
  if (!/\p{N}/u.test(value)) return `${label} must include at least one number.`;
  return undefined;
}

export function validateConfirmPassword(password: string, confirm: string): string | undefined {
  if (!confirm) return "Please re-enter your password.";
  if (password !== confirm) return "Passwords don't match.";
  return undefined;
}

export function validateCompanyName(value: string): string | undefined {
  const name = value.trim();
  if (!name) return "Company name is required.";
  if (name.length < 2) return "Company name must be at least 2 characters.";
  if (name.length > 120) return "Company name must be at most 120 characters.";
  if (!/[\p{L}\p{N}]/u.test(name)) return "Company name must include letters or numbers.";
  return undefined;
}

export function validateInviteCode(value: string): string | undefined {
  const code = value.trim();
  if (!code) return "Invite code is required.";
  if (code.length < 6) return "That doesn't look like a complete invite code.";
  if (code.length > 64) return "That invite code is too long. Paste it exactly as your admin sent it.";
  return undefined;
}
