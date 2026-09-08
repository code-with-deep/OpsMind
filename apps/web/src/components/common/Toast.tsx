import { useEffect, useState } from "react";
import { CheckCircle, XCircle, Info, X } from "lucide-react";

export type ToastVariant = "success" | "error" | "info";

export interface ToastItem {
  id: string;
  message: string;
  variant: ToastVariant;
}

interface ToastProps {
  toasts: ToastItem[];
  onDismiss: (id: string) => void;
}

const ICONS = {
  success: <CheckCircle className="w-4 h-4 shrink-0 text-emerald-400" />,
  error: <XCircle className="w-4 h-4 shrink-0 text-rose-400" />,
  info: <Info className="w-4 h-4 shrink-0 text-accent-400" />,
};

const STYLES = {
  success:
    "border-emerald-700/60 bg-emerald-950/80 text-emerald-100",
  error:
    "border-rose-700/60 bg-rose-950/80 text-rose-100",
  info:
    "border-accent-700/60 bg-surface-900/90 text-surface-100",
};

function SingleToast({
  toast,
  onDismiss,
}: {
  toast: ToastItem;
  onDismiss: (id: string) => void;
}) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // mount animation
    const show = setTimeout(() => setVisible(true), 10);
    // auto-dismiss
    const hide = setTimeout(() => {
      setVisible(false);
      setTimeout(() => onDismiss(toast.id), 300);
    }, 4000);
    return () => {
      clearTimeout(show);
      clearTimeout(hide);
    };
  }, [toast.id, onDismiss]);

  const handleDismiss = () => {
    setVisible(false);
    setTimeout(() => onDismiss(toast.id), 300);
  };

  return (
    <div
      className={`flex items-start gap-2.5 px-3.5 py-2.5 rounded-xl border backdrop-blur-xl shadow-xl text-sm max-w-sm w-full transition-all duration-300 ${
        STYLES[toast.variant]
      } ${visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-2"}`}
    >
      {ICONS[toast.variant]}
      <span className="flex-1 leading-snug">{toast.message}</span>
      <button
        type="button"
        onClick={handleDismiss}
        className="shrink-0 opacity-60 hover:opacity-100 transition-opacity mt-0.5"
        aria-label="Dismiss"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}

export function ToastContainer({ toasts, onDismiss }: ToastProps) {
  if (toasts.length === 0) return null;
  return (
    <div className="fixed bottom-5 right-4 z-50 flex flex-col gap-2 items-end pointer-events-none">
      {toasts.map((t) => (
        <div key={t.id} className="pointer-events-auto">
          <SingleToast toast={t} onDismiss={onDismiss} />
        </div>
      ))}
    </div>
  );
}
