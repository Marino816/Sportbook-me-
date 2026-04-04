"use client";

import React, { useEffect, useState } from "react";
import { Check, CreditCard, ExternalLink, Zap, Loader2, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { fetchSubscriptionStatus, createCheckout, createPortal, type SubscriptionStatus } from "@/lib/api";

export default function BillingPage() {
  const [sub, setSub] = useState<SubscriptionStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [showSuccess, setShowSuccess] = useState(false);
  const [showCanceled, setShowCanceled] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("success")) setShowSuccess(true);
    if (params.get("canceled")) setShowCanceled(true);
    
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

  const handleCheckout = async (plan: string) => {
    setActionLoading(plan);
    try {
      const res = await createCheckout(plan);
      if (res.data.url) {
        window.location.href = res.data.url;
      }
    } catch (e: any) {
      alert(e.message || "Could not initialize checkout.");
    } finally {
      setActionLoading(null);
    }
  };

  const handlePortal = async () => {
    setActionLoading('portal');
    try {
      const res = await createPortal();
      if (res.data.url) {
        window.location.href = res.data.url;
      }
    } catch (e: any) {
      alert(e.message || "Could not open customer portal.");
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-12">
        <Loader2 className="size-12 text-primary animate-spin mb-4" />
        <p className="text-muted-foreground font-black italic tracking-widest uppercase">Initializing Payment Gateway...</p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-8 h-full bg-background max-w-6xl mx-auto w-full">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-foreground tracking-tight underline decoration-primary/20">Billing & Subscription</h1>
        <p className="text-muted-foreground mt-1 text-sm uppercase tracking-widest font-black opacity-50">S P O R T S B O O K _ M E _ D F S _ A I</p>
      </div>

      {showSuccess && (
        <div className="mb-8 p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-xl flex items-center gap-3 text-emerald-400">
          <Check className="size-5" />
          <p className="font-medium">Subscription activated successfully! Your features are now unlocked.</p>
        </div>
      )}

      {showCanceled && (
        <div className="mb-8 p-4 bg-orange-500/10 border border-orange-500/20 rounded-xl flex items-center gap-3 text-orange-400">
          <AlertCircle className="size-5" />
          <p className="font-medium">Checkout was canceled. No charges were made.</p>
        </div>
      )}

      {sub?.plan !== "Starter" ? (
        <div className="glass rounded-2xl p-8 border border-border mb-12 flex flex-col md:flex-row justify-between items-start md:items-center shadow-lg shadow-primary/5">
          <div>
            <div className={cn(
              "inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm font-bold mb-4 uppercase italic tracking-tighter",
              sub?.plan === "Elite Stack" ? "bg-orange-500/20 text-orange-500" : "bg-primary/20 text-primary border border-primary/20"
            )}>
              <Zap className="size-4 fill-current" /> {sub?.plan}
            </div>
            <h2 className="text-2xl font-bold mb-1">{sub?.has_access ? "Active Subscription" : "Subscription Inactive"}</h2>
            <p className="text-muted-foreground mb-4 md:mb-0">
              {sub?.is_canceled 
                ? `Canceled. Access until: ${new Date(sub.next_billing!).toLocaleDateString()}`
                : `Next billing cycle: ${new Date(sub?.next_billing || "").toLocaleDateString()}`
              }
            </p>
          </div>
          <div className="flex gap-4 w-full md:w-auto">
            <button 
              onClick={handlePortal}
              disabled={!!actionLoading}
              className="flex-1 md:flex-none px-6 py-3 bg-secondary hover:bg-secondary/80 text-foreground border border-border font-medium rounded-xl transition-colors flex justify-center items-center gap-2 disabled:opacity-50"
            >
              {actionLoading === 'portal' ? <Loader2 className="size-4 animate-spin" /> : <CreditCard className="size-4" />}
              Manage in Stripe
            </button>
          </div>
        </div>
      ) : (
        <div className="bg-primary/5 border border-primary/20 rounded-2xl p-8 mb-12 flex items-center justify-between">
            <div className="flex items-center gap-4">
                <div className="size-12 bg-primary/10 rounded-xl flex items-center justify-center">
                    <Zap className="size-6 text-primary" />
                </div>
                <div>
                   <h2 className="text-xl font-bold italic tracking-tight uppercase">You are on the Starter Plan</h2>
                   <p className="text-sm text-foreground/60">Upgrade now to unlock 150-Max lineup generation and CSV exports.</p>
                </div>
            </div>
            <div className="hidden md:block">
                <div className="text-[10px] font-black tracking-widest text-primary/40 uppercase">A P E X _ T I E R _ 0 1</div>
            </div>
        </div>
      )}

      <h3 className="text-xl font-bold mb-6">Upgrade Plan</h3>
      
      <div className="grid md:grid-cols-2 gap-8 mb-12">
        {/* Pro Plan */}
        <div className={cn(
          "glass p-8 rounded-2xl border border-border flex flex-col h-full transition-all duration-300",
          sub?.plan === "Pro Arena" && "border-primary bg-primary/5 scale-[1.02]"
        )}>
          <h3 className="text-xl font-medium mb-2">Pro Arena</h3>
          <div className="text-3xl font-bold mb-6">$29<span className="text-base text-muted-foreground font-normal">/mo</span></div>
          
          <button 
            disabled={sub?.plan === "Pro Arena" || !!actionLoading}
            onClick={() => handleCheckout("Pro Arena")}
            className={cn(
              "w-full py-3 font-bold rounded-lg transition-all mb-8 shadow-lg",
              sub?.plan === "Pro Arena" 
                ? "bg-secondary text-muted-foreground cursor-not-allowed" 
                : "bg-primary text-primary-foreground hover:bg-primary/90 shadow-primary/20"
            )}
          >
            {actionLoading === "Pro Arena" ? <Loader2 className="size-4 animate-spin mx-auto" /> : (sub?.plan === "Pro Arena" ? "Current Plan" : "Upgrade to Pro")}
          </button>
          
          <ul className="space-y-4 flex-1">
            <Feature check text="Full Projs + Ownership" />
            <Feature check text="20 Lineup Max Generator" />
            <Feature check text="Basic CSV Exports" />
          </ul>
        </div>
        
        {/* Elite Plan */}
        <div className={cn(
            "p-8 rounded-2xl border border-primary bg-primary/5 shadow-xl shadow-primary/10 relative flex flex-col h-full transition-all duration-300",
            sub?.plan === "Elite Stack" && "border-orange-500/50 bg-orange-500/5 shadow-orange-500/10 scale-[1.02]"
        )}>
          <div className="absolute top-0 right-8 -translate-y-1/2 bg-gradient-to-r from-orange-400 to-primary text-white px-4 py-1 rounded-full text-xs font-bold uppercase tracking-wider shadow-lg">
            Recommended
          </div>
          <h3 className="text-xl font-medium mb-2 text-primary">Elite Stack</h3>
          <div className="text-3xl font-bold mb-6 text-white">$79<span className="text-base text-muted-foreground font-normal">/mo</span></div>
          
          <button 
             disabled={sub?.plan === "Elite Stack" || !!actionLoading}
             onClick={() => handleCheckout("Elite Stack")}
             className={cn(
                "w-full py-3 font-bold rounded-lg shadow-lg transition-all mb-8",
                sub?.plan === "Elite Stack"
                    ? "bg-secondary text-muted-foreground cursor-not-allowed"
                    : "bg-orange-500 hover:bg-orange-600 text-white shadow-orange-500/20"
             )}
          >
            {actionLoading === "Elite Stack" ? <Loader2 className="size-4 animate-spin mx-auto" /> : (sub?.plan === "Elite Stack" ? "Current Plan" : "Upgrade to Elite")}
          </button>
          
          <ul className="space-y-4 flex-1">
            <Feature check text="All Pro Tools + Elite Signals" highlight />
            <Feature check text="150-Max Multi-Generation" highlight />
            <Feature check text="DraftKings & FanDuel CSVs" highlight />
            <Feature check text="Optimizer Rules & Late Swap" highlight />
          </ul>
        </div>
      </div>

      <div className="glass rounded-2xl p-8 border border-border">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold">Billing History</h2>
          <button 
            onClick={handlePortal}
            className="text-sm text-primary hover:underline flex items-center gap-1"
          >
            View all invoices <ExternalLink className="size-3" />
          </button>
        </div>
        <div className="text-center py-8 text-muted-foreground text-sm border-2 border-dashed border-border/50 rounded-xl">
          Complete your first subscription to see invoice history.
        </div>
      </div>
    </div>
  );
}

function Feature({ text, check, highlight, pending }: any) {
  return (
    <li className="flex items-center gap-3">
      {check ? (
        <Check className={cn("size-5", highlight ? 'text-primary' : 'text-muted-foreground')} />
      ) : (
         <div className="size-5 rounded-full border border-muted-foreground/30 flex items-center justify-center flex-shrink-0">
           {pending && <div className="w-2.5 h-px bg-muted-foreground/30" />}
         </div>
      )}
      <span className={cn(highlight ? 'text-foreground font-medium' : 'text-muted-foreground')}>{text}</span>
    </li>
  );
}
