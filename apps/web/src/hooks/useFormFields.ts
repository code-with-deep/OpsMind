import { useState } from "react";

export type FieldErrors<K extends string> = Partial<Record<K, string>>;

/**
 * Form state with validate-on-blur/submit plus server-side field errors.
 * A field's error appears once the user has left it or tried to submit, so
 * nobody is scolded while still typing; editing a field clears its server error.
 */
export function useFormFields<K extends string>(
  initial: Record<K, string>,
  validate: (values: Record<K, string>) => FieldErrors<K>
) {
  const [values, setValues] = useState(initial);
  const [touched, setTouched] = useState<Partial<Record<K, boolean>>>({});
  const [submitted, setSubmitted] = useState(false);
  const [serverErrors, setServerErrors] = useState<FieldErrors<K>>({});

  const clientErrors = validate(values);
  const keys = Object.keys(initial) as K[];

  const errorFor = (key: K): string | undefined =>
    serverErrors[key] ?? (touched[key] || submitted ? clientErrors[key] : undefined);

  const setValue = (key: K, value: string) => {
    setValues((prev) => ({ ...prev, [key]: value }));
    setServerErrors((prev) => {
      if (!prev[key]) return prev;
      const next = { ...prev };
      delete next[key];
      return next;
    });
  };

  const focusField = (key: string) => document.getElementById(`field-${key}`)?.focus();

  /** Props for <TextField>. */
  const bind = (key: K) => ({
    id: `field-${key}`,
    name: key,
    value: values[key],
    onChange: (value: string) => setValue(key, value),
    onBlur: () => setTouched((prev) => ({ ...prev, [key]: true })),
    error: errorFor(key),
  });

  /** Marks the form as submitted; returns false and focuses the first invalid field when invalid. */
  const validateForSubmit = (): boolean => {
    setSubmitted(true);
    const firstInvalid = keys.find((key) => clientErrors[key]);
    if (firstInvalid) {
      focusField(firstInvalid);
      return false;
    }
    return true;
  };

  /** Shows server validation messages next to their fields; returns true if any matched. */
  const applyServerErrors = (fieldErrors: Record<string, string>): boolean => {
    const matched: FieldErrors<K> = {};
    for (const key of keys) if (fieldErrors[key]) matched[key] = fieldErrors[key];
    setServerErrors(matched);
    const first = keys.find((key) => matched[key]);
    if (first) focusField(first);
    return Boolean(first);
  };

  const reset = () => {
    setValues(initial);
    setTouched({});
    setSubmitted(false);
    setServerErrors({});
  };

  return { values, setValue, bind, validateForSubmit, applyServerErrors, reset };
}
