"use client";
import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { claimUsername } from "@/lib/api";
import { USERNAME_RULES, usernameFormatOk } from "@/lib/username";
import Link from "next/link";

export default function ProfilePage() {
  const { user, isAuthenticated, logout, refreshUser } = useAuth();
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const saveUsername = async () => {
    setError(null);
    if (!usernameFormatOk(draft)) {
      setError(USERNAME_RULES);
      return;
    }
    setSaving(true);
    try {
      await claimUsername(draft.trim());
      await refreshUser();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "That username is taken.");
    } finally {
      setSaving(false);
    }
  };

  if (!isAuthenticated) {
    return (
      <div style={{ background: "#0a0f24", minHeight: "100vh", padding: 32, color: "#f0f6fc" }}>
        <h1 style={{ fontSize: 28, fontWeight: 900, color: "#c9a84c", fontStyle: "italic" }}>Profile</h1>
        <div style={{ marginTop: 24, padding: 24, background: "#0a0f24", borderRadius: 16, border: "1px solid #1e293b" }}>
          <p style={{ color: "#94a3b8", marginBottom: 16 }}>Sign in to manage your profile and subscription.</p>
          <Link href="/login" style={{ background: "#c9a84c", color: "#0a0f24", padding: "12px 24px", borderRadius: 12, fontWeight: 700, textDecoration: "none" }}>
            Sign In
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div style={{ background: "#0a0f24", minHeight: "100vh", padding: 32, color: "#f0f6fc" }}>
      <h1 style={{ fontSize: 28, fontWeight: 900, color: "#c9a84c", fontStyle: "italic" }}>Profile</h1>

      <div style={{ marginTop: 24, display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{ background: "#0a0f24", borderRadius: 16, padding: 20, border: "1px solid #1e293b" }}>
          <span style={{ fontSize: 12, color: "#64748b", textTransform: "uppercase", fontWeight: 700 }}>Account</span>
          <p style={{ fontSize: 16, fontWeight: 700, color: "#f0f6fc", marginTop: 4 }}>{user?.email}</p>
          <p style={{ fontSize: 14, color: "#c9a84c", fontWeight: 600, marginTop: 2 }}>{user?.plan || "Free"} Plan</p>
          <div style={{ marginTop: 16 }}>
            <span style={{ fontSize: 12, color: "#64748b", textTransform: "uppercase", fontWeight: 700 }}>Username</span>
            {user?.username ? (
              <p style={{ fontSize: 16, fontWeight: 700, color: "#f0f6fc", marginTop: 4 }}>{user.username}</p>
            ) : (
              <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 8 }}>
                <input
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  placeholder="choose username"
                  style={{ padding: "10px 12px", borderRadius: 10, border: "1px solid #1e293b", background: "#060b1a", color: "#f0f6fc" }}
                />
                <button
                  type="button"
                  onClick={saveUsername}
                  disabled={saving}
                  style={{ background: "#c9a84c", color: "#0a0f24", padding: "10px 16px", borderRadius: 10, fontWeight: 700, border: "none", cursor: "pointer", width: "fit-content" }}
                >
                  {saving ? "Saving…" : "choose username"}
                </button>
                <p style={{ fontSize: 12, color: "#64748b" }}>{USERNAME_RULES} Once selected, it cannot be changed.</p>
                {error && <p style={{ fontSize: 13, color: "#ef4444" }}>{error}</p>}
              </div>
            )}
          </div>
        </div>

        <Link href="/billing" style={{
          background: "#0a0f24", borderRadius: 14, padding: "16px 20px", border: "1px solid #1e293b",
          color: "#c9a84c", fontWeight: 700, textDecoration: "none", display: "block",
        }}>
          Billing & Subscription
        </Link>

        <Link href="/settings" style={{
          background: "#0a0f24", borderRadius: 14, padding: "16px 20px", border: "1px solid #1e293b",
          color: "#94a3b8", fontWeight: 700, textDecoration: "none", display: "block",
        }}>
          Settings & AI Preferences
        </Link>

        <button onClick={logout} style={{
          background: "transparent", borderRadius: 14, padding: "16px 20px", border: "1px solid #ef444440",
          color: "#ef4444", fontWeight: 700, cursor: "pointer", textAlign: "left",
        }}>
          Sign Out
        </button>
      </div>
    </div>
  );
}