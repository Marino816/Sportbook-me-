"use client";

import { usePathname } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { MarketToolsApproved } from "@/components/market-tools-approved/MarketToolsApproved";
import { tabFromPath, useMarketToolsMode } from "@/lib/market-tools-mode";

export default function MarketToolsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const atmosphere = pathname === "/market-tools" ? "tools" : "app";
  const { provider } = useMarketToolsMode();

  if (provider === "oddsapi_snapshot" || provider === "oddsapi") {
    return (
      <AppShell atmosphere={atmosphere}>
        <MarketToolsApproved initialTab={tabFromPath(pathname)} />
      </AppShell>
    );
  }

  return <AppShell atmosphere={atmosphere}>{children}</AppShell>;
}
