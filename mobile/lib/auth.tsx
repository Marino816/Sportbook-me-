/**
 * Auth session for the Expo Router app.
 * Bootstrap validates JWT via GET /auth/me — a stored string is not enough.
 * JWT lives in expo-secure-store only.
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

export type AuthStatus = "loading" | "authenticated" | "unauthenticated" | "retrying";

type AuthContextValue = {
  status: AuthStatus;
  user: AuthUser | null;
  signIn: (identifier: string, password: string) => Promise<void>;
  signInWithBiometrics: () => Promise<void>;
  signOut: () => Promise<void>;
  refreshUser: () => Promise<void>;
  retryRestore: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

/** Share one restore across React Strict Mode remounts so a cancelled first pass is not lost. */
let inflightRestore: ReturnType<typeof restoreSession> | null = null;

function restoreSessionShared() {
  if (!inflightRestore) {
    inflightRestore = restoreSession().finally(() => {
      setTimeout(() => {
        inflightRestore = null;
      }, 0);
    });
  }
  return inflightRestore;
}

function applyRestore(
  session: Awaited<ReturnType<typeof restoreSession>>,
  setUser: (u: AuthUser | null) => void,
  setStatus: (s: AuthStatus) => void,
) {
  if (session.kind === "authenticated") {
    setUser(session.user);
    setStatus("authenticated");
    return;
  }
  if (session.kind === "transient") {
    setUser(null);
    setStatus("retrying");
    return;
  }
  setUser(null);
  setStatus("unauthenticated");
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<AuthUser | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const session = await restoreSessionShared();
        if (!active) return;
        applyRestore(session, setUser, setStatus);
      } catch {
        if (!active) return;
        const token = await getToken();
        if (token) {
          setUser(null);
          setStatus("retrying");
        } else {
          setUser(null);
          setStatus("unauthenticated");
        }
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  const retryRestore = useCallback(async () => {
    setStatus("loading");
    inflightRestore = null;
    try {
      const session = await restoreSession();
      applyRestore(session, setUser, setStatus);
    } catch {
      const token = await getToken();
      setUser(null);
      setStatus(token ? "retrying" : "unauthenticated");
    }
  }, []);

  const signIn = useCallback(async (identifier: string, password: string) => {
    await apiLogin(identifier, password);
    const session = await restoreSession();
    if (session.kind !== "authenticated") throw new Error("Could not establish session");
    setUser(session.user);
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
    if (session.kind !== "authenticated") throw new Error("Session expired. Please sign in with your password.");
    setUser(session.user);
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
    () => ({ status, user, signIn, signInWithBiometrics, signOut, refreshUser, retryRestore }),
    [status, user, signIn, signInWithBiometrics, signOut, refreshUser, retryRestore],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
