"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";

const PROTECTED_PATHS = [
  "/admin",
  "/ai",
  "/backtesting",
  "/billing",
  "/dashboard",
  "/data-hub",
  "/lineups",
  "/market-tools",
  "/optimizer",
  "/profile",
  "/projections",
  "/sims",
  "/top-stacks",
] as const;

function isProtectedPath(pathname: string): boolean {
  return PROTECTED_PATHS.some(
    (path) => pathname === path || pathname.startsWith(`${path}/`),
  );
}

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const requiresAuthentication = isProtectedPath(pathname);

  useEffect(() => {
    if (!requiresAuthentication || isLoading || isAuthenticated) return;

    const requestedPath = `${pathname}${window.location.search}`;
    router.replace(`/login?next=${encodeURIComponent(requestedPath)}`);
  }, [isAuthenticated, isLoading, pathname, requiresAuthentication, router]);

  if (requiresAuthentication && (isLoading || !isAuthenticated)) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#0a0f24] text-sm text-[#8b949e]">
        Checking your session…
      </div>
    );
  }

  return <>{children}</>;
}
