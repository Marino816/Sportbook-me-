"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { useAuth } from "@/lib/auth";
import { getSafeReturnPath } from "@/lib/safe-return-path";
import { checkUsernameAvailable } from "@/lib/api";
import { USERNAME_RULES, usernameFormatOk } from "@/lib/username";
import { Loader2, Mail, Lock, AlertCircle, UserRound } from "lucide-react";
import { SBMEBackground } from "@/components/sbme-background";

export default function RegisterPage() {
  const router = useRouter();
  const nextPath = typeof window === "undefined" ? null : new URLSearchParams(window.location.search).get("next");
  const destination = getSafeReturnPath(nextPath);
  const { register, isAuthenticated } = useAuth();

  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [availability, setAvailability] = useState<string | null>(null);

  useEffect(() => {
    if (isAuthenticated) router.replace(destination);
  }, [destination, isAuthenticated, router]);

  useEffect(() => {
    const value = username.trim();
    if (!value) {
      setAvailability(null);
      return;
    }
    if (!usernameFormatOk(value)) {
      setAvailability(USERNAME_RULES);
      return;
    }
    const handle = window.setTimeout(() => {
      checkUsernameAvailable(value).then((res) => {
        if (res.reason === "rate_limited") {
          setAvailability(null);
          return;
        }
        setAvailability(res.available ? "Available" : "That username is taken.");
      }).catch(() => setAvailability(null));
    }, 400);
    return () => window.clearTimeout(handle);
  }, [username]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!usernameFormatOk(username)) {
      setError(USERNAME_RULES);
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setLoading(true);
    try {
      await register(username.trim(), email.trim(), password);
      router.push(destination);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Registration failed.");
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
            <h1>CREATE YOUR SB ME ACCOUNT</h1>
          </div>

          {error && (
            <div className="sbme-login-error">
              <AlertCircle size={18} />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="sbme-login-form">
            <label>
              Username
              <div className="sbme-login-field">
                <UserRound size={16} />
                <input
                  type="text"
                  autoComplete="username"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="choose a username"
                />
              </div>
              {availability && (
                <p className={`sbme-login-hint${availability === "Available" ? " sbme-login-hint--ok" : ""}`}>
                  {availability}
                </p>
              )}
            </label>
            <label>
              Email
              <div className="sbme-login-field">
                <Mail size={16} />
                <input
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                />
              </div>
            </label>
            <label>
              Password
              <div className="sbme-login-field">
                <Lock size={16} />
                <input
                  type="password"
                  autoComplete="new-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Min 8 characters"
                />
              </div>
            </label>
            <label>
              Confirm Password
              <div className="sbme-login-field">
                <Lock size={16} />
                <input
                  type="password"
                  autoComplete="new-password"
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Re-enter password"
                />
              </div>
            </label>
            <button type="submit" className="sbme-login-submit" disabled={loading}>
              {loading ? <Loader2 size={18} className="animate-spin" /> : "Create Account"}
            </button>
          </form>

          <p className="sbme-login-footer">
            Already have an account?{" "}
            <Link href="/login">Sign In</Link>
          </p>
        </div>
      </div>
    </SBMEBackground>
  );
}
