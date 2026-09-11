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

/**
 * Same job as getErrorMessage, but for a request made with
 * responseType: "blob" (file downloads).
 *
 * On a failed download the server still replies with FastAPI's normal
 * JSON error body — but because the request asked for a blob, axios
 * hands back error.response.data as a Blob rather than a parsed
 * object, so getErrorMessage sees no .detail and falls through to its
 * generic message. Reading the blob's text first recovers the real
 * reason (e.g. "Candidate profile not found"), which is exactly the
 * detail a user needs when a download button appears to do nothing.
 *
 * Async because Blob.text() is; callers must await it.
 */
export async function getBlobErrorMessage(error) {
  const data = error.response?.data;
  if (data instanceof Blob) {
    try {
      const parsed = JSON.parse(await data.text());
      if (typeof parsed.detail === "string") return parsed.detail;
      if (Array.isArray(parsed.detail)) return parsed.detail.map((d) => d.msg).join("; ");
    } catch {
      // Not JSON (an HTML error page, or an empty body from a network
      // failure) — fall through to the shared generic message.
    }
  }
  return getErrorMessage(error);
}
