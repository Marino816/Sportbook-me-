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
    plan: string;
    isPro: boolean;
    role: string;
  } | null;
  isLoading: boolean;
  isAuthenticated: boolean;
}

interface AuthContextType extends AuthState {
  isAdmin: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
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
      .then((res) => {
        setState({
          user: {
            email: res.data.email,
            plan: res.data.plan || "Starter",
            isPro: res.data.is_pro || false,
            role: res.data.role || "user",
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

  const login = useCallback(async (email: string, password: string) => {
    const tokens: AuthTokens = await apiLogin(email, password);
    storeToken(tokens.access_token);
    setState({
      user: {
        email: tokens.email,
        plan: tokens.plan,
        isPro: tokens.plan !== "Starter",
        role: tokens.role || "user",
      },
      isLoading: false,
      isAuthenticated: true,
    });
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    const tokens: AuthTokens = await apiRegister(email, password);
    storeToken(tokens.access_token);
    setState({
      user: {
        email: tokens.email,
        plan: tokens.plan,
        isPro: false,
        role: tokens.role || "user",
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
      value={{ ...state, isAdmin, login, register, logout }}
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
