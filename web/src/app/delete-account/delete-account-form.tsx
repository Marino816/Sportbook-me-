"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { deleteAccount } from "@/lib/api";
import { gold } from "@/components/legal/legal-page";

const navy = "#0a0f24";
const border = "#1e293b";
const textPrimary = "#f0f6fc";
const textSecondary = "#94a3b8";

export function DeleteAccountForm() {
  const { isAuthenticated, isLoading, logout } = useAuth();
  const [typed, setTyped] = useState("");
  const [understood, setUnderstood] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  if (isLoading) {
    return <p style={{ color: textSecondary, fontSize: 14 }}>Checking your session…</p>;
  }

  if (done) {
    return (
      <div style={{ background: navy, border: `1px solid ${border}`, borderRadius: 16, padding: 20, margin: "24px 0" }}>
        <p style={{ color: gold, fontWeight: 800, fontSize: 18, marginBottom: 8 }}>Account deleted</p>
        <p style={{ color: textSecondary, fontSize: 14, lineHeight: 1.6 }}>
          Your Sportbook Me DFS AI account was deleted in this request. You are signed out.
        </p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div style={{ background: navy, border: `1px solid ${gold}`, borderRadius: 16, padding: 20, margin: "24px 0" }}>
        <p style={{ color: textPrimary, fontWeight: 800, fontSize: 18, marginBottom: 8 }}>
          Request account deletion
        </p>
        <p style={{ color: textSecondary, fontSize: 14, lineHeight: 1.6, marginBottom: 16 }}>
          Sign in on this website with the Sportbook Me DFS AI account you want deleted. That sign-in verifies
          ownership. After you sign in you return here to confirm, and deletion runs immediately — this is not
          a form that only shows a success message.
        </p>
        <Link
          href="/login?next=/delete-account"
          style={{ background: gold, color: navy, padding: "12px 20px", borderRadius: 12, fontWeight: 800, textDecoration: "none", display: "inline-block" }}
        >
          Sign in to request deletion
        </Link>
      </div>
    );
  }

  const canSubmit = understood && typed.trim() === "DELETE" && !busy;

  async function onDelete() {
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    try {
      await deleteAccount();
      logout();
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Account deletion failed");
      setBusy(false);
    }
  }

  return (
    <div style={{ background: navy, border: "1px solid #ef444440", borderRadius: 16, padding: 20, margin: "24px 0" }}>
      <p style={{ color: "#ef4444", fontWeight: 800, fontSize: 16, marginBottom: 8 }}>Permanently delete this account</p>
      <p style={{ color: textSecondary, fontSize: 14, lineHeight: 1.6, marginBottom: 12 }}>
        You are signed in. Submitting this request deletes the Sportbook Me DFS AI account for this session now.
        This cannot be undone.
      </p>
      <label style={{ display: "flex", gap: 10, alignItems: "flex-start", color: textSecondary, fontSize: 14, marginBottom: 14 }}>
        <input type="checkbox" checked={understood} onChange={(e) => setUnderstood(e.target.checked)} />
        <span>I understand this permanently deletes my Sportbook Me DFS AI account and does not cancel Apple, Google Play, or Stripe billing.</span>
      </label>
      <label style={{ display: "block", color: textSecondary, fontSize: 13, marginBottom: 8 }}>
        Type DELETE to confirm
      </label>
      <input
        value={typed}
        onChange={(e) => setTyped(e.target.value)}
        placeholder="DELETE"
        autoComplete="off"
        style={{ width: "100%", maxWidth: 280, padding: "10px 12px", borderRadius: 10, border: `1px solid ${border}`, background: "#060b1a", color: textPrimary, marginBottom: 14 }}
      />
      {error && <p style={{ color: "#ef4444", fontSize: 13, marginBottom: 12 }}>{error}</p>}
      <button
        type="button"
        onClick={onDelete}
        disabled={!canSubmit}
        style={{
          background: canSubmit ? "#ef4444" : "#1e293b",
          color: canSubmit ? "#fff" : "#64748b",
          padding: "12px 20px",
          borderRadius: 12,
          fontWeight: 800,
          border: "none",
          cursor: canSubmit ? "pointer" : "not-allowed",
        }}
      >
        {busy ? "Deleting…" : "Permanently delete account"}
      </button>
    </div>
  );
}
