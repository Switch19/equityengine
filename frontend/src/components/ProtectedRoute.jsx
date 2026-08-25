import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

/**
 * Wraps a route so it requires login, and optionally a specific role.
 * Mirrors the backend's require_role() dependency — the frontend
 * check is a UX convenience (redirect before a wasted API round
 * trip), not a security boundary; the backend enforces the real one.
 */
export function ProtectedRoute({ children, allowedRole }) {
  const { user } = useAuth();

  if (!user) {
    return <Navigate to="/login" replace />;
  }
  if (allowedRole && user.role !== allowedRole) {
    return <Navigate to="/" replace />;
  }
  return children;
}
