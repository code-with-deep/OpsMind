import { useState, type FocusEvent } from "react";

export type FieldErrors<K extends string> = Partial<Record<K, string>>;

// Whether a mouse/touch press is in progress, shared by every form. Pressing a
// link or button blurs the focused field; if its error appeared right away the
// layout would shift, the press would be released over a different spot and the
// browser would drop the click — so the link only worked on the second click.
let pointerPressed = false;
if (typeof window !== "undefined") {
  const release = () => {
    pointerPressed = false;
  };
  window.addEventListener("pointerdown", () => { pointerPressed = true; }, true);
  window.addEventListener("pointerup", release, true);
  window.addEventListener("pointercancel", release, true);
  window.addEventListener("blur", release);
}

/** Runs `fn` now, or after the click that ends a press in progress. */
function afterPointerRelease(fn: () => void): void {
  if (!pointerPressed) {
    fn();
    return;
  }
  const run = () => {
    window.removeEventListener("pointerup", run, true);
    window.removeEventListener("pointercancel", run, true);
    // A timer runs after the click event that follows pointerup.
    setTimeout(fn, 0);
  };
  window.addEventListener("pointerup", run, true);
  window.addEventListener("pointercancel", run, true);
}

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
    onBlur: (e: FocusEvent<HTMLInputElement>) => {
      // Autofill may have filled the input without an onChange; pick its value
      // up before the field is marked touched so no false "required" flashes.
      const domValue = e.currentTarget.value;
      if (domValue !== values[key]) setValue(key, domValue);
      afterPointerRelease(() => setTouched((prev) => ({ ...prev, [key]: true })));
    },
    error: errorFor(key),
  });

  /**
   * Marks the form as submitted and validates what the inputs actually hold.
   * Browser autofill can fill inputs without firing onChange (Chrome withholds the
   * value until the user interacts with the page), so state may still be empty.
   * Returns the values to submit, or null (focusing the first invalid field).
   */
  const validateForSubmit = (): Record<K, string> | null => {
    const current = { ...values };
    for (const key of keys) {
      const input = document.getElementById(`field-${key}`);
      if (input instanceof HTMLInputElement) current[key] = input.value;
    }
    setValues(current);
    setSubmitted(true);
    const errors = validate(current);
    const firstInvalid = keys.find((key) => errors[key]);
    if (firstInvalid) {
      focusField(firstInvalid);
      return null;
    }
    return current;
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
