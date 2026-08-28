"use client";

import { SBMEBackground } from "./sbme-background";

export function AppShell({
  children,
  atmosphere = "app",
}: {
  children: React.ReactNode;
  atmosphere?: "app" | "home" | "tools";
}) {
  return (
    <SBMEBackground variant={atmosphere} className="min-h-screen">
      {children}
    </SBMEBackground>
  );
}
