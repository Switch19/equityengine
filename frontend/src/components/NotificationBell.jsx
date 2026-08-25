import { useState, useEffect, useCallback, useRef } from "react";
import { notificationsApi } from "../api/messages";
import { useWebSocketContext } from "../context/WebSocketContext";
import { useToast } from "../context/ToastContext";
import { getErrorMessage } from "../api/client";

export default function NotificationBell() {
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifications, setNotifications] = useState([]);
  const [open, setOpen] = useState(false);
  const { subscribe } = useWebSocketContext();
  const { showToast } = useToast();
  const dropdownRef = useRef(null);

  const loadUnreadCount = useCallback(async () => {
    try {
      const res = await notificationsApi.getUnreadCount();
      setUnreadCount(res.data.unread_count);
    } catch {
      // Silent — a failed unread-count fetch shouldn't interrupt the
      // rest of the page with an error toast.
    }
  }, []);

  const loadNotifications = useCallback(async () => {
    try {
      const res = await notificationsApi.getAll();
      setNotifications(res.data);
    } catch (error) {
      showToast(getErrorMessage(error), "error");
    }
  }, [showToast]);

  useEffect(() => {
    loadUnreadCount();
  }, [loadUnreadCount]);

  useEffect(() => {
    const unsubscribe = subscribe("notification", () => {
      setUnreadCount((prev) => prev + 1);
    });
    return unsubscribe;
  }, [subscribe]);

  useEffect(() => {
    function handleClickOutside(e) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  async function handleOpen() {
    const next = !open;
    setOpen(next);
    if (next) {
      await loadNotifications();
    }
  }

  async function handleMarkAllRead() {
    try {
      await notificationsApi.markAllRead();
      setUnreadCount(0);
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
    } catch (error) {
      showToast(getErrorMessage(error), "error");
    }
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={handleOpen}
        className="relative p-2 rounded hover:bg-ink-50 transition-colors"
        aria-label="Notifications"
      >
        <BellIcon />
        {unreadCount > 0 && (
          <span className="absolute top-0.5 right-0.5 bg-gap text-white text-[10px] font-bold rounded-full min-w-[16px] h-4 flex items-center justify-center px-1">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-80 bg-white border border-ink-100 rounded-lg shadow-lg z-50 max-h-96 overflow-y-auto">
          <div className="flex items-center justify-between px-4 py-3 border-b border-ink-100">
            <p className="font-medium text-sm">Notifications</p>
            {unreadCount > 0 && (
              <button onClick={handleMarkAllRead} className="text-xs text-slate underline underline-offset-2">
                Mark all read
              </button>
            )}
          </div>

          {notifications.length === 0 ? (
            <p className="text-sm text-slate text-center py-8">No notifications yet.</p>
          ) : (
            <ul>
              {notifications.map((n) => (
                <li
                  key={n.id}
                  className={`px-4 py-3 text-sm border-b border-ink-50 last:border-0 ${
                    !n.is_read ? "bg-beacon-50" : ""
                  }`}
                >
                  <p className="text-ink">{n.message}</p>
                  <p className="text-xs text-slate mt-1">
                    {new Date(n.created_at).toLocaleString()}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

function BellIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M10 2C7.5 2 5.5 4 5.5 6.5V9.5L4 12.5H16L14.5 9.5V6.5C14.5 4 12.5 2 10 2Z"
        stroke="#14163A"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path d="M8 15C8 16.1 8.9 17 10 17C11.1 17 12 16.1 12 15" stroke="#14163A" strokeWidth="1.5" />
    </svg>
  );
}
