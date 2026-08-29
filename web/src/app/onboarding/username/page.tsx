"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { useAuth } from "@/lib/auth";
import { claimUsername } from "@/lib/api";
import { USERNAME_RULES, usernameFormatOk } from "@/lib/username";
import { AlertCircle, Loader2, UserRound } from "lucide-react";
import { SBMEBackground } from "@/components/sbme-background";

export default function ChooseUsernamePage() {
  const router = useRouter();
  const { user, isAuthenticated, refreshUser } = useAuth();
  const [username, setUsername] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (isAuthenticated && user?.username) {
    router.replace("/dashboard");
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!usernameFormatOk(username)) {
      setError(USERNAME_RULES);
      return;
    }
    setLoading(true);
    try {
      await claimUsername(username.trim());
      await refreshUser();
      router.replace("/dashboard");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "That username is taken.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <SBMEBackground variant="hero" className="sbme-login-page">
      <div className="sbme-login-wrap">
        <div className="sbme-login-card">
          <div className="sbme-login-brand">
            <Image src="/logo.png" alt="SB ME" width={140} height={74} priority />
            <h1>Choose your username</h1>
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
            </label>
            <p className="sbme-login-hint">{USERNAME_RULES} This cannot be changed later.</p>
            <button type="submit" className="sbme-login-submit" disabled={loading}>
              {loading ? <Loader2 size={18} className="animate-spin" /> : "Save username"}
            </button>
          </form>
        </div>
      </div>
    </SBMEBackground>
  );
}
