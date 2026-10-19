"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Check, CreditCard, Zap, Loader2, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  fetchSubscriptionStatus,
  createPortal,
  cancelSubscription,
  type SubscriptionStatus,
} from "@/lib/api";

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

function providerLabel(sub: SubscriptionStatus | null) {
  return sub?.provider_display || (sub?.provider === "paykings" ? "PayKings" : sub?.provider === "stripe" ? "Stripe" : "None");
}

export default function BillingPage() {
  const [sub, setSub] = useState<SubscriptionStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [cancelMessage, setCancelMessage] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetchSubscriptionStatus();
        setSub(res.data);
      } catch (e: any) {
        setError(e.message || "Failed to load subscription data.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const handlePortal = async () => {
    setActionLoading("portal");
    setError(null);
    try {
      const res = await createPortal();
      if (res.data.url) {
        window.location.href = res.data.url;
      }
    } catch (e: any) {
      setError(e.message || "Could not open customer portal.");
    } finally {
      setActionLoading(null);
    }
  };

  const handleCancel = async () => {
    setActionLoading("cancel");
    setError(null);
    setCancelMessage(null);
    try {
      const res = await cancelSubscription();
      const next = res.data;
      if (!next.processor_confirmed) {
        setError("The payment processor did not confirm cancellation. Renewal was not marked canceled.");
        return;
      }
      setSub(next);
      setConfirmOpen(false);
      setCancelMessage(next.processor_message || "Cancellation confirmed with the payment processor. Paid-through access is unchanged.");
    } catch (e: any) {
      setError(e.message || "Cancellation failed at the payment processor.");
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-12">
        <Loader2 className="size-12 text-primary animate-spin mb-4" />
        <p className="text-muted-foreground font-black italic tracking-widest uppercase">Loading billing...</p>
      </div>
    );
  }

  const stripeManaged = sub?.provider === "stripe";
  const hasPaidPlan = Boolean(sub?.plan && sub.plan !== "Starter");

  return (
    <div className="flex-1 overflow-y-auto p-8 h-full bg-background max-w-6xl mx-auto w-full">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-foreground tracking-tight underline decoration-primary/20">Billing & Subscription</h1>
        <p className="text-muted-foreground mt-1 text-sm uppercase tracking-widest font-black opacity-50">S P O R T S B O O K _ M E _ D F S _ A I</p>
      </div>

      {error && (
        <div className="mb-8 p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-center gap-3 text-red-400">
          <AlertCircle className="size-5" />
          <p className="font-medium">{error}</p>
        </div>
      )}

      {cancelMessage && (
        <div className="mb-8 p-4 bg-primary/10 border border-primary/20 rounded-xl flex items-center gap-3 text-primary">
          <Check className="size-5" />
          <p className="font-medium">{cancelMessage}</p>
        </div>
      )}

      {sub?.purchases_paused && (
        <div className="mb-8 p-4 bg-orange-500/10 border border-orange-500/20 rounded-xl flex items-center gap-3 text-orange-400">
          <AlertCircle className="size-5" />
          <p className="font-medium">New purchases and upgrades are paused. You can still manage your existing subscription, profile, and account deletion.</p>
        </div>
      )}

      {hasPaidPlan ? (
        <div className="glass rounded-2xl p-8 border border-border mb-12 flex flex-col gap-6 shadow-lg shadow-primary/5">
          <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
            <div>
              <div className={cn(
                "inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm font-bold mb-4 uppercase italic tracking-tighter",
                sub?.plan?.startsWith("Elite") ? "bg-orange-500/20 text-orange-500" : "bg-primary/20 text-primary border border-primary/20"
              )}>
                <Zap className="size-4 fill-current" /> {sub?.plan}
              </div>
              <h2 className="text-2xl font-bold mb-1">{sub?.has_access ? "Active Subscription" : "Subscription Inactive"}</h2>
              <p className="text-3xl font-bold mt-2">{formatAmount(sub?.amount, sub?.billing_interval)}</p>
            </div>
            <div className="flex flex-col gap-3 w-full md:w-auto">
              {stripeManaged && (
                <button
                  onClick={handlePortal}
                  disabled={!!actionLoading}
                  className="px-6 py-3 bg-secondary hover:bg-secondary/80 text-foreground border border-border font-medium rounded-xl transition-colors flex justify-center items-center gap-2 disabled:opacity-50"
                >
                  {actionLoading === "portal" ? <Loader2 className="size-4 animate-spin" /> : <CreditCard className="size-4" />}
                  Manage in Stripe
                </button>
              )}
              {sub?.can_cancel && (
                <button
                  onClick={() => setConfirmOpen(true)}
                  disabled={!!actionLoading}
                  className="px-6 py-3 bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/30 font-medium rounded-xl transition-colors disabled:opacity-50"
                >
                  Cancel subscription
                </button>
              )}
            </div>
          </div>
          <dl className="grid sm:grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="text-muted-foreground uppercase tracking-widest text-xs font-bold">Payment provider</dt>
              <dd className="font-medium mt-1">{providerLabel(sub)}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground uppercase tracking-widest text-xs font-bold">Billing interval</dt>
              <dd className="font-medium mt-1 capitalize">{sub?.billing_interval || "—"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground uppercase tracking-widest text-xs font-bold">Renewal status</dt>
              <dd className="font-medium mt-1">
                {sub?.is_canceled ? "Canceled. No future renewal." : "Renews automatically"}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground uppercase tracking-widest text-xs font-bold">Paid through</dt>
              <dd className="font-medium mt-1">{formatBillingDate(sub?.paid_through)}</dd>
            </div>
          </dl>
          {sub?.is_canceled && (
            <p className="text-muted-foreground text-sm">
              Cancellation confirmed. Access continues through {formatBillingDate(sub?.paid_through)}.
            </p>
          )}
        </div>
      ) : (
        <div className="bg-primary/5 border border-primary/20 rounded-2xl p-8 mb-12">
          <h2 className="text-xl font-bold italic tracking-tight uppercase">You are on the Starter Plan</h2>
          <p className="text-sm text-foreground/60 mt-2">New purchases and upgrades are paused. Existing account management and deletion remain available.</p>
        </div>
      )}

      <div className="glass rounded-2xl p-8 border border-border">
        <h2 className="text-xl font-bold mb-2">Account</h2>
        <p className="text-sm text-muted-foreground mb-4">Profile, settings, and account deletion stay available during the pause.</p>
        <div className="flex flex-wrap gap-3">
          <Link href="/profile" className="px-4 py-2 rounded-lg border border-border text-sm font-medium hover:bg-secondary">Profile</Link>
          <Link href="/delete-account" className="px-4 py-2 rounded-lg border border-red-500/30 text-sm font-medium text-red-400 hover:bg-red-500/10">Delete account</Link>
        </div>
      </div>

      {confirmOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
          <div className="bg-background border border-border rounded-2xl p-6 max-w-md w-full">
            <h3 className="text-xl font-bold mb-2">Cancel renewal?</h3>
            <p className="text-sm text-muted-foreground mb-6">
              This stops future charges with {providerLabel(sub)}. You keep access through {formatBillingDate(sub?.paid_through)}. This does not issue a refund.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setConfirmOpen(false)}
                disabled={actionLoading === "cancel"}
                className="px-4 py-2 rounded-lg border border-border"
              >
                Keep subscription
              </button>
              <button
                onClick={handleCancel}
                disabled={actionLoading === "cancel"}
                className="px-4 py-2 rounded-lg bg-red-500 text-white font-medium disabled:opacity-50"
              >
                {actionLoading === "cancel" ? <Loader2 className="size-4 animate-spin" /> : "Confirm cancel"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
