"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { useAuth } from "@/lib/auth";
import { getSafeReturnPath } from "@/lib/safe-return-path";
import { fetchAuthProviders, oauthStartUrl, type AuthProviderStatus } from "@/lib/api";
import { Loader2, Lock, AlertCircle, UserRound } from "lucide-react";
import { SBMEBackground } from "@/components/sbme-background";

function providerReady(p: AuthProviderStatus): boolean {
  return Boolean(p.configured ?? p.enabled);
}

export default function LoginPage() {
  const router = useRouter();
  const nextPath = typeof window === "undefined" ? null : new URLSearchParams(window.location.search).get("next");
  const destination = getSafeReturnPath(nextPath);
  const { login, isAuthenticated } = useAuth();

  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [google, setGoogle] = useState<AuthProviderStatus>({ enabled: false, configured: false, status: "pending" });
  const [apple, setApple] = useState<AuthProviderStatus>({ enabled: false, configured: false, status: "pending" });

  useEffect(() => {
    if (isAuthenticated) router.replace(destination);
  }, [destination, isAuthenticated, router]);

  useEffect(() => {
    let cancelled = false;
    fetchAuthProviders().then((p) => {
      if (cancelled) return;
      setGoogle(p.google);
      setApple(p.apple);
    }).catch(() => { /* keep pending */ });
    return () => { cancelled = true; };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(identifier.trim(), password);
      router.push(destination);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Invalid username/email or password.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <SBMEBackground variant="hero" className="sbme-login-page">
      <div className="sbme-login-wrap">
        <div className="sbme-login-card">
          <div className="sbme-login-brand">
            <Link href="/">
              <Image src="/logo.png" alt="SB ME" width={140} height={74} priority />
            </Link>
            <h1>WELCOME TO SB ME</h1>
          </div>

          {error && (
            <div className="sbme-login-error">
              <AlertCircle size={18} />
              <span>{error}</span>
            </div>
          )}

          <OAuthButton
            label="Continue with Google"
            ready={providerReady(google)}
            reason={google.reason}
            href={oauthStartUrl("google")}
          />
          <OAuthButton
            label="Continue with Apple"
            ready={providerReady(apple)}
            reason={apple.reason}
            href={oauthStartUrl("apple")}
          />

          <div className="sbme-login-or"><span>or</span></div>

          <form onSubmit={handleSubmit} className="sbme-login-form">
            <label>
              Username or Email
              <div className="sbme-login-field">
                <UserRound size={16} />
                <input
                  type="text"
                  autoComplete="username"
                  required
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  placeholder="username or email"
                />
              </div>
            </label>
            <label>
              Password
              <div className="sbme-login-field">
                <Lock size={16} />
                <input
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                />
              </div>
            </label>
            <button type="submit" className="sbme-login-submit" disabled={loading}>
              {loading ? <Loader2 size={18} className="animate-spin" /> : "LOG IN"}
            </button>
          </form>

          <p className="sbme-login-forgot">
            Forgot password? Password reset is unavailable until mail delivery is configured.
          </p>
          <p className="sbme-login-footer">
            Don&apos;t have an account?{" "}
            <Link href="/register">Create account</Link>
          </p>
        </div>
      </div>
    </SBMEBackground>
  );
}

function OAuthButton({
  label,
  ready,
  reason,
  href,
}: {
  label: string;
  ready: boolean;
  reason?: string | null;
  href: string;
}) {
  if (ready) {
    return (
      <a className="sbme-login-oauth sbme-login-oauth--ready" href={href}>
        {label}
      </a>
    );
  }
  return (
    <button type="button" className="sbme-login-oauth" disabled title={reason || "Coming soon"}>
      {label}
      <span>Coming soon</span>
    </button>
  );
}
