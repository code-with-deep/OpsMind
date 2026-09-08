import { useCallback, useState } from "react";
import type { ToastItem, ToastVariant } from "../components/common/Toast";

let _nextId = 0;

export function useToast() {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const toast = useCallback(
    (message: string, variant: ToastVariant = "info") => {
      const id = String(++_nextId);
      setToasts((prev) => [...prev, { id, message, variant }]);
    },
    []
  );

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return { toasts, toast, dismiss };
}
