"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { ApiError, api } from "@/lib/api";
import { clearStoredToken, getStoredToken, setRefreshToken, setStoredToken } from "@/lib/auth";
import type { TokenResponse, UserProfile } from "@/types/api";

interface AuthContextValue {
  user: UserProfile | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (payload: { email: string; password: string }) => Promise<TokenResponse>;
  register: (payload: {
    email: string;
    password: string;
    full_name: string;
  }) => Promise<TokenResponse>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    const token = getStoredToken();
    if (!token) {
      setUser(null);
      setIsLoading(false);
      return;
    }
    try {
      const me = await api.me();
      setUser(me);
    } catch (error) {
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        try {
          const refreshed = await api.refresh();
          setStoredToken(refreshed.access_token);
          if (refreshed.refresh_token) setRefreshToken(refreshed.refresh_token);
          setUser(refreshed.user);
        } catch {
          clearStoredToken();
          setUser(null);
        }
      } else {
        setUser(null);
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshUser();
  }, [refreshUser]);

  const completeAuth = useCallback((response: TokenResponse) => {
    setStoredToken(response.access_token);
    if (response.refresh_token) setRefreshToken(response.refresh_token);
    setUser(response.user);
    setIsLoading(false);
    return response;
  }, []);

  const login = useCallback(
    async (payload: { email: string; password: string }) => completeAuth(await api.login(payload)),
    [completeAuth],
  );

  const register = useCallback(
    async (payload: { email: string; password: string; full_name: string }) =>
      completeAuth(await api.register(payload)),
    [completeAuth],
  );

  const logout = useCallback(() => {
    void api.logout().catch(() => undefined);
    clearStoredToken();
    setUser(null);
    setIsLoading(false);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isLoading,
      isAuthenticated: user !== null,
      login,
      register,
      logout,
      refreshUser,
    }),
    [isLoading, login, logout, refreshUser, register, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error("useAuth must be used within AuthProvider.");
  }
  return context;
}
