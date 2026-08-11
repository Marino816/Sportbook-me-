"use client";
import { useAuth } from "@/lib/auth";
import Link from "next/link";

export default function AIPage() {
  const { user } = useAuth();
  return (
    <div style={{ background: "#060b1a", minHeight: "100vh", padding: 32, color: "#f0f6fc" }}>
      <h1 style={{ fontSize: 28, fontWeight: 900, color: "#c9a84c", fontStyle: "italic" }}>SB ME AI</h1>
      <p style={{ color: "#94a3b8", marginTop: 8 }}>AI-Powered DFS Intelligence — ask anything about your lineups, players, and market signals.</p>
      {!user && (
        <div style={{ marginTop: 24, padding: 24, background: "#0a0f24", borderRadius: 16, border: "1px solid #1e293b" }}>
          <p style={{ color: "#94a3b8", marginBottom: 16 }}>Sign in to access SB ME AI.</p>
          <Link href="/login" style={{ background: "#c9a84c", color: "#060b1a", padding: "12px 24px", borderRadius: 12, fontWeight: 700, textDecoration: "none" }}>
            Sign In
          </Link>
        </div>
      )}
    </div>
  );
}