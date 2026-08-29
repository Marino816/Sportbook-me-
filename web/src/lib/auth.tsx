"use client";

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
} from "react";
import {
  login as apiLogin,
  register as apiRegister,
  fetchCurrentUser,
  storeToken,
  clearToken,
  getStoredToken,
  type AuthTokens,
} from "./api";

interface AuthState {
  user: {
    email: string;
    username: string | null;
    plan: string;
    isPro: boolean;
    role: string;
  } | null;
  isLoading: boolean;
  isAuthenticated: boolean;
}

interface AuthContextType extends AuthState {
  isAdmin: boolean;
  login: (identifier: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string) => Promise<void>;
  applyToken: (token: string) => Promise<void>;
  refreshUser: () => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    isLoading: true,
    isAuthenticated: false,
  });

  // Check for existing token on mount
  useEffect(() => {
    const token = getStoredToken();
    if (!token) {
      setState({ user: null, isLoading: false, isAuthenticated: false });
      return;
    }

    // Validate the stored token
    fetchCurrentUser()
      .then((user) => {
        const plan = user.plan || "Starter";
        setState({
          user: {
            email: user.email,
            username: user.username || null,
            plan,
            isPro: Boolean(user.is_pro) || plan !== "Starter",
            role: user.role || "user",
          },
          isLoading: false,
          isAuthenticated: true,
        });
      })
      .catch(() => {
        // Token invalid or expired — clear it
        clearToken();
        setState({ user: null, isLoading: false, isAuthenticated: false });
      });
  }, []);

  const login = useCallback(async (identifier: string, password: string) => {
    const tokens: AuthTokens = await apiLogin(identifier, password);
    storeToken(tokens.access_token);
    setState({
      user: {
        email: tokens.email,
        username: tokens.username || null,
        plan: tokens.plan,
        isPro: tokens.plan !== "Starter",
        role: tokens.role || "user",
      },
      isLoading: false,
      isAuthenticated: true,
    });
  }, []);

  const register = useCallback(async (username: string, email: string, password: string) => {
    const tokens: AuthTokens = await apiRegister(username, email, password);
    storeToken(tokens.access_token);
    setState({
      user: {
        email: tokens.email,
        username: tokens.username || username,
        plan: tokens.plan,
        isPro: false,
        role: tokens.role || "user",
      },
      isLoading: false,
      isAuthenticated: true,
    });
  }, []);

  const applyToken = useCallback(async (token: string) => {
    storeToken(token);
    const user = await fetchCurrentUser();
    const plan = user.plan || "Starter";
    setState({
      user: {
        email: user.email,
        username: user.username || null,
        plan,
        isPro: Boolean(user.is_pro) || plan !== "Starter",
        role: user.role || "user",
      },
      isLoading: false,
      isAuthenticated: true,
    });
  }, []);

  const refreshUser = useCallback(async () => {
    const user = await fetchCurrentUser();
    const plan = user.plan || "Starter";
    setState({
      user: {
        email: user.email,
        username: user.username || null,
        plan,
        isPro: Boolean(user.is_pro) || plan !== "Starter",
        role: user.role || "user",
      },
      isLoading: false,
      isAuthenticated: true,
    });
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setState({ user: null, isLoading: false, isAuthenticated: false });
  }, []);

  const isAdmin = state.user?.role === "admin";

  return (
    <AuthContext.Provider
      value={{ ...state, isAdmin, login, register, applyToken, refreshUser, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
