import { createContext, useContext, useEffect, useRef, useCallback } from "react";
import { useAuth } from "./AuthContext";
import { getWebSocketUrl } from "../api/client";

const WebSocketContext = createContext(null);

/**
 * One shared WebSocket connection for the whole app, rather than each
 * page opening its own. Components subscribe to specific event types
 * (e.g. "new_message", "notification") via subscribe() and get an
 * unsubscribe function back — this is a pub/sub pattern, not a
 * context value that changes on every message, so subscribing
 * components don't need to re-render the whole app on every event.
 *
 * Reconnection: on an unexpected close, retries after a fixed 3s
 * delay rather than exponential backoff — simpler, and reasonable
 * for a single-user-testing-locally FYP demo. A production system
 * serving many concurrent users would want backoff to avoid a
 * reconnection storm after a server restart; not a concern at this
 * project's scale.
 */
export function WebSocketProvider({ children }) {
  const { user } = useAuth();
  const wsRef = useRef(null);
  const listenersRef = useRef({});
  const reconnectTimerRef = useRef(null);

  const dispatch = useCallback((eventType, payload) => {
    const listeners = listenersRef.current[eventType] || [];
    listeners.forEach((cb) => cb(payload));
  }, []);

  const connect = useCallback(() => {
    if (!user) return;

    const ws = new WebSocket(getWebSocketUrl());
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        dispatch(data.event, data);
      } catch {
        // Ignore malformed frames rather than crashing the connection.
      }
    };

    ws.onclose = (event) => {
      // 4001/4003 are our own auth-failure/deactivated-account codes
      // (see backend/app/routers/ws.py) — don't retry those, since
      // reconnecting with the same token will just fail again.
      if (event.code === 4001 || event.code === 4003) return;
      reconnectTimerRef.current = setTimeout(connect, 3000);
    };
  }, [user, dispatch]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimerRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const subscribe = useCallback((eventType, callback) => {
    if (!listenersRef.current[eventType]) {
      listenersRef.current[eventType] = [];
    }
    listenersRef.current[eventType].push(callback);
    return () => {
      listenersRef.current[eventType] = listenersRef.current[eventType].filter((cb) => cb !== callback);
    };
  }, []);

  const sendChatMessage = useCallback((receiverId, jobId, content) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ receiver_id: receiverId, job_id: jobId, content }));
      return true;
    }
    return false; // caller should fall back to the REST /messages/send endpoint
  }, []);

  return (
    <WebSocketContext.Provider value={{ subscribe, sendChatMessage }}>
      {children}
    </WebSocketContext.Provider>
  );
}

export function useWebSocketContext() {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error("useWebSocketContext must be used within a WebSocketProvider");
  }
  return context;
}
