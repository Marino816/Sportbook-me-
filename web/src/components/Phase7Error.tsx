"use client";

import React from "react";

type ErrorKind =
  | "loading"
  | "no-data"
  | "unauthorized"
  | "forbidden"
  | "not-found"
  | "rate-limited"
  | "server-error"
  | "timeout"
  | "network"
  | "stale-data"
  | "missing-data"
  | "provider-unavailable"
  | "demo-data";

interface Phase7ErrorProps {
  kind: ErrorKind;
  message?: string;
  onRetry?: () => void;
}

const ERROR_STATES: Record<ErrorKind, { title: string; className: string }> = {
  loading: { title: "Loading\u2026", className: "border-border" },
  "no-data": { title: "No Data Available", className: "border-border" },
  unauthorized: { title: "Sign In Required", className: "border-red-500/30" },
  forbidden: { title: "Access Denied \u2014 Upgrade Required", className: "border-amber-500/30" },
  "not-found": { title: "Resource Unavailable", className: "border-border" },
  "rate-limited": { title: "Request Limit Reached", className: "border-yellow-500/30" },
  "server-error": { title: "Service Error", className: "border-red-500/30" },
  timeout: { title: "Request Timed Out", className: "border-yellow-500/30" },
  network: { title: "Network Error", className: "border-red-500/30" },
  "stale-data": { title: "Data May Be Stale", className: "border-yellow-500/30" },
  "missing-data": { title: "Missing Data Fields", className: "border-yellow-500/30" },
  "provider-unavailable": { title: "Data Provider Unavailable", className: "border-red-500/30" },
  "demo-data": { title: "DEMO DATA \u2014 NOT LIVE", className: "border-amber-500/50 bg-amber-500/10" },
};

export default function Phase7Error({ kind, message, onRetry }: Phase7ErrorProps) {
  const state = ERROR_STATES[kind];
  return (
    <div className={`rounded-2xl border p-6 ${state.className} text-center`}>
      <p className="font-bold text-sm mb-1">{state.title}</p>
      {message && <p className="text-xs text-muted mb-3">{message}</p>}
      {onRetry && kind !== "loading" && (
        <button onClick={onRetry} className="text-xs underline hover:no-underline">Retry</button>
      )}
    </div>
  );
}

export function isErrorStatus(status: number): ErrorKind {
  if (status === 401) return "unauthorized";
  if (status === 403) return "forbidden";
  if (status === 404) return "not-found";
  if (status === 422) return "missing-data";
  if (status === 429) return "rate-limited";
  if (status >= 500) return "server-error";
  return "server-error";
}

export function shouldShowDemo(): boolean {
  if (typeof window === "undefined") return false;
  return process.env.NEXT_PUBLIC_ENABLE_DEMO_DATA === "true";
}