"use client";

import { usePathname } from "next/navigation";
import { AppShell } from "@/components/app-shell";

export default function MarketToolsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const atmosphere = pathname === "/market-tools" ? "tools" : "app";
  return <AppShell atmosphere={atmosphere}>{children}</AppShell>;
}
