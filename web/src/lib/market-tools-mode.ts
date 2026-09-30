"use client";

import { getApiBaseUrl } from "@/lib/api-base-url";
import { getStoredToken } from "@/lib/api";
import { useCallback, useEffect, useState } from "react";

export type MarketToolsProvider = "sgo" | "oddsapi_snapshot";

export function tabFromPath(pathname: string): "live" | "compare" | "props" | "parlay" {
  if (pathname.includes("/compare") || pathname.includes("/arbitrage")) return "compare";
  if (pathname.includes("/player-props")) return "props";
  if (pathname.includes("/parlay")) return "parlay";
  return "live";
}

export function useMarketToolsMode() {
  const [provider, setProvider] = useState<MarketToolsProvider | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) {
      setProvider("sgo");
      return;
    }
    const base = getApiBaseUrl(process.env.NEXT_PUBLIC_API_URL);
    try {
      const res = await fetch(`${base}/market-tools/internal/status`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        setProvider("sgo");
        return;
      }
      const json = await res.json();
      const next = json?.data?.provider === "oddsapi_snapshot" ? "oddsapi_snapshot" : "sgo";
      setProvider(next);
    } catch {
      setError("status_unavailable");
      setProvider("sgo");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return { provider, error, reload: load };
}
