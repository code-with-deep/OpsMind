import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { ChangeEvent, ConnectionState, connectRealtime, RealtimeEvent } from "../lib/realtime";

type Listener = (event: RealtimeEvent) => void;

interface RealtimeContextValue {
  state: ConnectionState;
  subscribe: (listener: Listener) => () => void;
}

const RealtimeContext = createContext<RealtimeContextValue | null>(null);

/** Opens one live-update stream for the signed-in app and shares it with every page. */
export function RealtimeProvider({ children }: { children: ReactNode }) {
  const listeners = useRef(new Set<Listener>());
  const [state, setState] = useState<ConnectionState>("connecting");

  useEffect(
    () =>
      connectRealtime({
        onEvent: (event) => listeners.current.forEach((listener) => listener(event)),
        onStateChange: setState,
      }),
    []
  );

  const subscribe = useCallback((listener: Listener) => {
    listeners.current.add(listener);
    return () => {
      listeners.current.delete(listener);
    };
  }, []);

  const value = useMemo(() => ({ state, subscribe }), [state, subscribe]);
  return <RealtimeContext.Provider value={value}>{children}</RealtimeContext.Provider>;
}

/** Live connection state; "offline" outside a RealtimeProvider (public pages). */
export function useRealtimeState(): ConnectionState {
  return useContext(RealtimeContext)?.state ?? "offline";
}

interface LiveRefreshOptions {
  enabled?: boolean;
  debounceMs?: number;
}

/**
 * Calls `onChange` when the server reports changes to any of `tables`, batched
 * over `debounceMs`. An empty batch means "resynced after a reconnect — anything
 * may have changed", so callers should refetch.
 */
export function useLiveRefresh(
  tables: readonly string[],
  onChange: (events: ChangeEvent[]) => void,
  { enabled = true, debounceMs = 300 }: LiveRefreshOptions = {}
): void {
  const subscribe = useContext(RealtimeContext)?.subscribe;
  const callback = useRef(onChange);
  callback.current = onChange;
  const tableKey = tables.join(",");

  useEffect(() => {
    if (!subscribe || !enabled) return;
    const watched = new Set(tableKey.split(","));
    let pending: ChangeEvent[] = [];
    let resync = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const flush = () => {
      timer = null;
      const batch = resync ? [] : pending;
      pending = [];
      resync = false;
      callback.current(batch);
    };

    const unsubscribe = subscribe((event) => {
      if (event.type === "resync") resync = true;
      else if (watched.has(event.table)) pending.push(event);
      else return;
      if (!timer) timer = setTimeout(flush, debounceMs);
    });

    return () => {
      unsubscribe();
      if (timer) clearTimeout(timer);
    };
  }, [subscribe, enabled, tableKey, debounceMs]);
}
