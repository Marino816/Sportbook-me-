"use client";
import { useAuth } from "@/lib/auth";
import Link from "next/link";

export default function LineupsPage() {
  const { user } = useAuth();
  return (
    <div style={{ background: "#060b1a", minHeight: "100vh", padding: 32, color: "#f0f6fc" }}>
      <h1 style={{ fontSize: 28, fontWeight: 900, color: "#c9a84c", fontStyle: "italic" }}>Lineups</h1>
      <p style={{ color: "#94a3b8", marginTop: 8 }}>Your saved lineup history across all sports and platforms.</p>
      {!user ? (
        <div style={{ marginTop: 24, padding: 24, background: "#0a0f24", borderRadius: 16, border: "1px solid #1e293b" }}>
          <p style={{ color: "#94a3b8", marginBottom: 16 }}>Sign in to view your lineup history.</p>
          <Link href="/login" style={{ background: "#c9a84c", color: "#060b1a", padding: "12px 24px", borderRadius: 12, fontWeight: 700, textDecoration: "none" }}>
            Sign In
          </Link>
        </div>
      ) : (
        <p style={{ color: "#64748b", marginTop: 24 }}>No lineups yet. Head to the Optimizer to build your first lineup.</p>
      )}
    </div>
  );
}