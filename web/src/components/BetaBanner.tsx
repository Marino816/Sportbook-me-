"use client";

/**
 * Closed beta banner — shown to all beta users during invite-only phase.
 * Dismissible. Displays beta status and feedback link.
 */

import { useState, useEffect } from "react";
import Link from "next/link";

export default function BetaBanner() {
  const [visible, setVisible] = useState(true);
  const [isBeta, setIsBeta] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("sbme_dfs_token");
    if (!token) return;
    try {
      const payload = JSON.parse(atob(token.split(".")[1]));
      if (payload.is_beta || payload.role === "admin") {
        setIsBeta(true);
      }
    } catch {
      // Token not valid — hide banner
    }
  }, []);

  if (!visible || !isBeta) return null;

  return (
    <div className="bg-yellow-500/10 border-b border-yellow-500/20 px-4 py-2 text-center text-xs" role="banner" aria-label="Closed beta">
      <span className="font-semibold text-yellow-400">Closed Beta</span>
      <span className="text-muted-foreground ml-2">Invite-only · Your feedback shapes the product.</span>
      <Link href="mailto:qa@sportbookme.ai" className="ml-2 underline">Send Feedback</Link>
      <button onClick={() => setVisible(false)} className="ml-3 text-muted-foreground hover:text-white" aria-label="Dismiss beta banner">✕</button>
    </div>
  );
}