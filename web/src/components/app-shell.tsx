"use client";

import { SBMEBackground } from "./sbme-background";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <SBMEBackground variant="app" className="min-h-screen">
      {children}
    </SBMEBackground>
  );
}
