import axios from "axios";

// The backend runs on 127.0.0.1:8000 by default (see backend/SETUP.md).
// Change this if you run the API on a different host/port.
const API_BASE_URL = "http://127.0.0.1:8000";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("equityengine_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// A 401 means the token is missing/expired/invalid — clear it and
// force a re-login rather than letting the app sit in a broken state
// where every subsequent request also silently fails.
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("equityengine_token");
      localStorage.removeItem("equityengine_user");
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

/**
 * Extracts a human-readable message from a FastAPI error response.
 * FastAPI validation errors (422) have a different shape than a plain
 * HTTPException (400/403/404/etc.) — this normalises both so every
 * page can show a sensible message without repeating this logic.
 */
export function getErrorMessage(error) {
  const detail = error.response?.data?.detail;
  if (!detail) return "Something went wrong. Please try again.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // Pydantic validation error format: [{loc, msg, type}, ...]
    return detail.map((d) => d.msg).join("; ");
  }
  return "Something went wrong. Please try again.";
}

export function getWebSocketUrl() {
  const token = localStorage.getItem("equityengine_token");
  return `ws://127.0.0.1:8000/ws/connect?token=${token}`;
}
