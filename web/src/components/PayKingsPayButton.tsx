"use client";

import React, { useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import { createPayKingsSubscribe } from "@/lib/api";
import {
  getPayKingsTokenizationKey,
  isSupportedPayKingsPlanId,
  loadCollectJs,
  type PayKingsPlanId,
} from "@/lib/paykings";

type Props = {
  planId: PayKingsPlanId;
  disabled?: boolean;
  className?: string;
  label: string;
};

export function PayKingsPayButton({ planId, disabled, className, label }: Props) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const planRef = useRef<PayKingsPlanId>(planId);
  planRef.current = planId;

  const startCheckout = async () => {
    setError(null);
    setMessage(null);
    if (!isSupportedPayKingsPlanId(planId)) {
      setError("That plan is not available.");
      return;
    }
    const key = getPayKingsTokenizationKey();
    if (!key) {
      setError("Card checkout is not configured yet. You can still use Stripe.");
      return;
    }
    setBusy(true);
    try {
      await loadCollectJs(key);
      if (!window.CollectJS) {
        throw new Error("Collect.js failed to load");
      }
      window.CollectJS.configure({
        paymentType: "cc",
        callback: (response) => {
          const token = response?.token;
          if (!token) {
            setBusy(false);
            setError("Card tokenization failed. No payment was submitted.");
            return;
          }
          void submitToken(planRef.current, token);
        },
      });
      window.CollectJS.startPaymentRequest();
      setBusy(false);
    } catch {
      setBusy(false);
      setError("Could not load the secure payment form.");
    }
  };

  const submitToken = async (selectedPlan: PayKingsPlanId, paymentToken: string) => {
    setBusy(true);
    setError(null);
    try {
      const res = await createPayKingsSubscribe(selectedPlan, paymentToken);
      const status = res.data?.status;
      if (status === "submitted" || status === "bound" || res.data?.provider_approved) {
        setMessage("Payment submitted. Your subscription is being confirmed.");
      } else {
        setMessage("Payment submitted. Your subscription is being confirmed.");
      }
    } catch (e: unknown) {
      const text = e instanceof Error ? e.message : "Payment could not be completed.";
      setError(text.includes("502") ? "PayKings declined or could not complete this subscription." : text);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-2">
      <button
        type="button"
        disabled={disabled || busy}
        onClick={() => void startCheckout()}
        className={className}
      >
        {busy ? <Loader2 className="size-4 animate-spin mx-auto" /> : label}
      </button>
      {message && (
        <p className="text-xs text-primary font-medium text-center">{message}</p>
      )}
      {error && (
        <p className="text-xs text-orange-400 font-medium text-center">{error}</p>
      )}
    </div>
  );
}
