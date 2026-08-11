"use client";
import { useAuth } from "@/lib/auth";
import Link from "next/link";

export default function ProfilePage() {
  const { user, isAuthenticated, logout } = useAuth();

  if (!isAuthenticated) {
    return (
      <div style={{ background: "#060b1a", minHeight: "100vh", padding: 32, color: "#f0f6fc" }}>
        <h1 style={{ fontSize: 28, fontWeight: 900, color: "#c9a84c", fontStyle: "italic" }}>Profile</h1>
        <div style={{ marginTop: 24, padding: 24, background: "#0a0f24", borderRadius: 16, border: "1px solid #1e293b" }}>
          <p style={{ color: "#94a3b8", marginBottom: 16 }}>Sign in to manage your profile and subscription.</p>
          <Link href="/login" style={{ background: "#c9a84c", color: "#060b1a", padding: "12px 24px", borderRadius: 12, fontWeight: 700, textDecoration: "none" }}>
            Sign In
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div style={{ background: "#060b1a", minHeight: "100vh", padding: 32, color: "#f0f6fc" }}>
      <h1 style={{ fontSize: 28, fontWeight: 900, color: "#c9a84c", fontStyle: "italic" }}>Profile</h1>

      <div style={{ marginTop: 24, display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{ background: "#0a0f24", borderRadius: 16, padding: 20, border: "1px solid #1e293b" }}>
          <span style={{ fontSize: 12, color: "#64748b", textTransform: "uppercase", fontWeight: 700 }}>Account</span>
          <p style={{ fontSize: 16, fontWeight: 700, color: "#f0f6fc", marginTop: 4 }}>{user?.email}</p>
          <p style={{ fontSize: 14, color: "#c9a84c", fontWeight: 600, marginTop: 2 }}>{user?.plan || "Free"} Plan</p>
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