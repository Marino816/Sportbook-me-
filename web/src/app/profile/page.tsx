"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import Link from "next/link";
import { fetchSubscriptionStatus, type SubscriptionStatus } from "@/lib/api";

function formatBillingDate(iso: string | null | undefined) {
  if (!iso) return "—";
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return "—";
  return parsed.toLocaleDateString("en-US", {
    timeZone: "UTC",
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

function formatAmount(amount: number | null | undefined, interval: string | null | undefined) {
  if (amount == null) return "—";
  const formatted = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(amount);
  if (interval === "annual") return `${formatted}/year`;
  if (interval === "monthly") return `${formatted}/month`;
  return formatted;
}

export default function ProfilePage() {
  const { user, isAuthenticated, logout } = useAuth();
  const [billing, setBilling] = useState<SubscriptionStatus | null>(null);

  useEffect(() => {
    if (!isAuthenticated) return;
    fetchSubscriptionStatus()
      .then((res) => setBilling(res.data))
      .catch(() => setBilling(null));
  }, [isAuthenticated]);

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
          <p style={{ fontSize: 14, color: "#c9a84c", fontWeight: 600, marginTop: 2 }}>{billing?.plan || user?.plan || "Free"} Plan</p>
        </div>

        <div style={{ background: "#0a0f24", borderRadius: 16, padding: 20, border: "1px solid #1e293b" }}>
          <span style={{ fontSize: 12, color: "#64748b", textTransform: "uppercase", fontWeight: 700 }}>Subscription</span>
          <p style={{ fontSize: 14, color: "#f0f6fc", marginTop: 8 }}>Amount: {formatAmount(billing?.amount, billing?.billing_interval)}</p>
          <p style={{ fontSize: 14, color: "#f0f6fc", marginTop: 4 }}>Interval: {billing?.billing_interval || "—"}</p>
          <p style={{ fontSize: 14, color: "#f0f6fc", marginTop: 4 }}>Provider: {billing?.provider_display || billing?.provider || "—"}</p>
          <p style={{ fontSize: 14, color: "#f0f6fc", marginTop: 4 }}>
            Renewal: {billing?.is_canceled ? "Canceled" : (billing?.renewal_status || "—")}
          </p>
          <p style={{ fontSize: 14, color: "#f0f6fc", marginTop: 4 }}>Paid through: {formatBillingDate(billing?.paid_through)}</p>
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

        <Link href="/delete-account" style={{
          background: "#0a0f24", borderRadius: 14, padding: "16px 20px", border: "1px solid #ef444440",
          color: "#ef4444", fontWeight: 700, textDecoration: "none", display: "block",
        }}>
          DELETE ACCOUNT
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
