import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, CheckCheck, Settings2 } from "lucide-react";
import { api, NotificationItem } from "../../lib/api";
import { routes } from "../../lib/routes";

const POLL_INTERVAL_MS = 30_000;

interface NotificationBellProps {
  className?: string;
}

function relativeTime(isoDate: string): string {
  const diff = Date.now() - new Date(isoDate).getTime();
  const secs = Math.floor(diff / 1000);
  if (secs < 60) return "just now";
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function NotificationBell({ className = "" }: NotificationBellProps) {
  const navigate = useNavigate();
  const [unreadCount, setUnreadCount] = useState(0);
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [loadingList, setLoadingList] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  // Poll unread count
  useEffect(() => {
    let mounted = true;
    const fetchCount = async () => {
      try {
        const res = await api.getUnreadCount();
        if (mounted) setUnreadCount(res.count);
      } catch {
        // silently ignore — user may not be logged in yet
      }
    };
    void fetchCount();
    const interval = setInterval(() => void fetchCount(), POLL_INTERVAL_MS);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  // Load notification list when panel opens
  useEffect(() => {
    if (!open) return;
    setLoadingList(true);
    api
      .listNotifications(10)
      .then((res) => setNotifications(res.notifications))
      .catch(() => setNotifications([]))
      .finally(() => setLoadingList(false));
  }, [open]);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const handleMarkRead = async (id: string) => {
    try {
      await api.markNotificationRead(id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      );
      setUnreadCount((c) => Math.max(0, c - 1));
    } catch {
      // ignore
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await api.markAllNotificationsRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch {
      // ignore
    }
  };

  const handleNotificationClick = async (n: NotificationItem) => {
    if (!n.is_read) {
      await handleMarkRead(n.id);
    }
    // Navigate to settings access management for access request notifications
    if (
      n.type === "access_request_submitted" ||
      n.related_entity_type === "access_request"
    ) {
      setOpen(false);
      navigate(routes.settings + "#access");
    }
  };

  return (
    <div className={`relative ${className}`} ref={panelRef}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ""}`}
        className="relative flex items-center justify-center w-9 h-9 rounded-lg bg-surface-900/80 border border-surface-700 text-surface-300 hover:text-white hover:border-surface-600 transition-colors focus:outline-none focus:ring-2 focus:ring-accent-500/40"
      >
        <Bell className="w-4 h-4" />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 flex items-center justify-center min-w-[16px] h-4 px-0.5 rounded-full bg-rose-500 text-white text-[9px] font-bold tabular-nums leading-none">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-80 sm:w-96 z-50 animate-fadeIn">
          <div className="app-panel rounded-xl border border-surface-700/60 shadow-2xl overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-surface-800">
              <span className="font-app-heading text-sm text-white">Notifications</span>
              {unreadCount > 0 && (
                <button
                  type="button"
                  onClick={() => void handleMarkAllRead()}
                  className="flex items-center gap-1 text-xs text-accent-400 hover:text-accent-300 transition-colors"
                >
                  <CheckCheck className="w-3.5 h-3.5" />
                  Mark all read
                </button>
              )}
            </div>

            {/* List */}
            <div className="max-h-80 overflow-y-auto">
              {loadingList ? (
                <div className="px-4 py-6 text-center text-xs text-surface-400">Loading…</div>
              ) : notifications.length === 0 ? (
                <div className="px-4 py-8 text-center">
                  <Bell className="w-8 h-8 text-surface-700 mx-auto mb-2" />
                  <p className="text-xs text-surface-500">No notifications</p>
                </div>
              ) : (
                <ul className="divide-y divide-surface-800/60">
                  {notifications.map((n) => (
                    <li
                      key={n.id}
                      className={`px-4 py-3 cursor-pointer transition-colors hover:bg-surface-800/40 ${
                        !n.is_read ? "bg-accent-950/20" : ""
                      }`}
                      onClick={() => void handleNotificationClick(n)}
                    >
                      <div className="flex items-start gap-2.5">
                        {/* Unread indicator */}
                        <span
                          className={`mt-1.5 shrink-0 w-1.5 h-1.5 rounded-full ${
                            !n.is_read ? "bg-accent-400" : "bg-surface-700"
                          }`}
                        />
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-medium text-surface-100 leading-snug">
                            {n.title}
                          </p>
                          <p className="text-xs text-surface-400 mt-0.5 leading-snug line-clamp-2">
                            {n.body}
                          </p>
                          <div className="flex items-center gap-2 mt-1">
                            <span className="text-[10px] text-surface-500">
                              {relativeTime(n.created_at)}
                            </span>
                            {(n.type === "access_request_submitted" ||
                              n.related_entity_type === "access_request") && (
                              <span className="flex items-center gap-1 text-[10px] text-accent-400">
                                <Settings2 className="w-2.5 h-2.5" />
                                View in Settings
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
