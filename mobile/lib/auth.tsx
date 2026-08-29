/**
 * Auth session for the Expo Router app.
 * Bootstrap validates JWT via GET /auth/me — a stored string is not enough.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import * as LocalAuthentication from "expo-local-authentication";
import {
  login as apiLogin,
  restoreSession,
  clearToken,
  getToken,
  getMe,
  unwrapUser,
  type AuthUser,
} from "./api";

export type AuthStatus = "loading" | "authenticated" | "unauthenticated";

type AuthContextValue = {
  status: AuthStatus;
  user: AuthUser | null;
  signIn: (identifier: string, password: string) => Promise<void>;
  signInWithBiometrics: () => Promise<void>;
  signOut: () => Promise<void>;
  refreshUser: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<AuthUser | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const session = await restoreSession();
        if (cancelled) return;
        if (session) {
          setUser(session);
          setStatus("authenticated");
        } else {
          setUser(null);
          setStatus("unauthenticated");
        }
      } catch {
        if (!cancelled) {
          setUser(null);
          setStatus("unauthenticated");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const signIn = useCallback(async (identifier: string, password: string) => {
    await apiLogin(identifier, password);
    const session = await restoreSession();
    if (!session) throw new Error("Could not establish session");
    setUser(session);
    setStatus("authenticated");
  }, []);

  const signInWithBiometrics = useCallback(async () => {
    const hasHW = await LocalAuthentication.hasHardwareAsync();
    if (!hasHW) throw new Error("Biometric login not available on this device");
    const enrolled = await LocalAuthentication.isEnrolledAsync();
    if (!enrolled) throw new Error("No biometrics enrolled");
    const existing = await getToken();
    if (!existing) throw new Error("Please log in first to enable biometric login");
    const result = await LocalAuthentication.authenticateAsync({
      promptMessage: "Sign in to SPORTBOOK ME",
    });
    if (!result.success) throw new Error("Biometric authentication cancelled");
    const session = await restoreSession();
    if (!session) throw new Error("Session expired. Please sign in with your password.");
    setUser(session);
    setStatus("authenticated");
  }, []);

  const signOut = useCallback(async () => {
    await clearToken();
    setUser(null);
    setStatus("unauthenticated");
  }, []);

  const refreshUser = useCallback(async () => {
    try {
      const next = unwrapUser(await getMe());
      if (next) setUser(next);
    } catch {
      // Keep current session; 401 is handled on the next restore / request.
    }
  }, []);

  const value = useMemo(
    () => ({ status, user, signIn, signInWithBiometrics, signOut, refreshUser }),
    [status, user, signIn, signInWithBiometrics, signOut, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
