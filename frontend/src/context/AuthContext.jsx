import { createContext, useContext, useState, useCallback } from "react";
import { apiClient, getErrorMessage } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem("equityengine_user");
    return stored ? JSON.parse(stored) : null;
  });
  const [loading, setLoading] = useState(false);

  const persistSession = useCallback((token, userData) => {
    localStorage.setItem("equityengine_token", token);
    localStorage.setItem("equityengine_user", JSON.stringify(userData));
    setUser(userData);
  }, []);

  const login = useCallback(
    async (email, password) => {
      setLoading(true);
      try {
        const response = await apiClient.post("/auth/login", { email, password });
        persistSession(response.data.access_token, response.data.user);
        return response.data.user;
      } catch (error) {
        throw new Error(getErrorMessage(error));
      } finally {
        setLoading(false);
      }
    },
    [persistSession]
  );

  const register = useCallback(
    async ({ email, fullName, password, role, consentGiven }) => {
      setLoading(true);
      try {
        const response = await apiClient.post("/auth/register", {
          email,
          full_name: fullName,
          password,
          role,
          consent_given: consentGiven,
        });
        persistSession(response.data.access_token, response.data.user);
        return response.data.user;
      } catch (error) {
        throw new Error(getErrorMessage(error));
      } finally {
        setLoading(false);
      }
    },
    [persistSession]
  );

  const logout = useCallback(() => {
    localStorage.removeItem("equityengine_token");
    localStorage.removeItem("equityengine_user");
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
