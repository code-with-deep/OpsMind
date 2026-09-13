import { authHeaders, getApiBaseUrl } from "./api";

/** A row changed on the server. Payload carries ids only — refetch via the API. */
export type ChangeEvent = {
  type: "change";
  table: string;
  op: "insert" | "update" | "delete";
  id: string | null;
  investigation_id: string | null;
};

/** Updates may have been missed (reconnect, backlog) — refetch everything. */
export type ResyncEvent = { type: "resync" };

export type RealtimeEvent = ChangeEvent | ResyncEvent;

export type ConnectionState = "connecting" | "live" | "offline";

type ConnectOptions = {
  onEvent: (event: RealtimeEvent) => void;
  onStateChange?: (state: ConnectionState) => void;
};

function parseEventBlock(block: string): RealtimeEvent | null {
  let name = "message";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) name = line.slice(6).trim();
    else if (line.startsWith("data:")) data.push(line.slice(5).trim());
  }
  if (name === "resync") return { type: "resync" };
  if (name !== "change" || data.length === 0) return null;
  try {
    return { type: "change", ...JSON.parse(data.join("\n")) } as ChangeEvent;
  } catch {
    return null;
  }
}

/**
 * Opens GET /events/stream and reconnects with backoff until the returned
 * function is called. Uses fetch streaming rather than EventSource because the
 * stream needs the Authorization header.
 */
export function connectRealtime({ onEvent, onStateChange }: ConnectOptions): () => void {
  let stopped = false;
  let controller: AbortController | null = null;
  let retryTimer: ReturnType<typeof setTimeout> | null = null;
  let attempt = 0;
  let hasConnected = false;

  const setState = (state: ConnectionState) => {
    if (!stopped) onStateChange?.(state);
  };

  const scheduleReconnect = () => {
    if (stopped || retryTimer) return;
    setState("offline");
    const delay = Math.min(30_000, 1_000 * 2 ** attempt) + Math.random() * 500;
    attempt += 1;
    retryTimer = setTimeout(() => {
      retryTimer = null;
      void connect();
    }, delay);
  };

  const connect = async () => {
    if (stopped) return;
    const headers = authHeaders();
    if (!headers.has("Authorization") && !headers.has("X-API-Key")) {
      setState("offline");
      return;
    }
    controller = new AbortController();
    setState("connecting");
    try {
      const response = await fetch(`${getApiBaseUrl()}/events/stream`, {
        headers,
        cache: "no-store",
        signal: controller.signal,
      });
      if (response.status === 401 || response.status === 403) {
        // Credentials are gone; regular API calls handle the sign-out redirect.
        setState("offline");
        return;
      }
      if (!response.ok || !response.body) throw new Error(`event stream HTTP ${response.status}`);

      attempt = 0;
      setState("live");
      if (hasConnected) onEvent({ type: "resync" }); // catch up on anything missed
      hasConnected = true;

      const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
      let buffer = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += value.replace(/\r\n/g, "\n");
        let boundary = buffer.indexOf("\n\n");
        while (boundary >= 0) {
          const event = parseEventBlock(buffer.slice(0, boundary));
          buffer = buffer.slice(boundary + 2);
          if (event) onEvent(event);
          boundary = buffer.indexOf("\n\n");
        }
      }
    } catch {
      if (stopped) return;
    }
    // Stream ended (server rotates streams periodically) or failed — reconnect.
    scheduleReconnect();
  };

  const reconnectNow = () => {
    if (stopped) return;
    if (retryTimer) {
      clearTimeout(retryTimer);
      retryTimer = null;
    }
    attempt = 0;
    controller?.abort();
    void connect();
  };

  window.addEventListener("online", reconnectNow);
  void connect();

  return () => {
    stopped = true;
    window.removeEventListener("online", reconnectNow);
    if (retryTimer) clearTimeout(retryTimer);
    controller?.abort();
  };
}
