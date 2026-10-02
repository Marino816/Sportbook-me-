"use client";

import { usePathname } from "next/navigation";
import { MarketToolsApproved } from "@/components/market-tools-approved/MarketToolsApproved";
import { tabFromPath, useMarketToolsMode } from "@/lib/market-tools-mode";

export default function MarketToolsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { provider } = useMarketToolsMode();

  // origin/main has no AppShell. Keep the existing SGO pages while flags are off.
  if (provider === "oddsapi_snapshot" || provider === "oddsapi") {
    return <MarketToolsApproved initialTab={tabFromPath(pathname)} />;
  }

  return children;
}
