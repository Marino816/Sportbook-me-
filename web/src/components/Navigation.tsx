"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  LayoutDashboard,
  Calculator,
  Activity,
  CreditCard,
  Settings,
  Zap,
  Users,
  LogOut,
  UserPlus,
  LogIn,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { useEffect, useState, Suspense } from "react";

const SPORTS = [
  { id: "nfl", label: "NFL", emoji: "🏈", color: "#d4ac0d" },
  { id: "nba", label: "NBA", emoji: "🏀", color: "#f97316" },
  { id: "mlb", label: "MLB", emoji: "⚾", color: "#3b82f6" },
  { id: "nhl", label: "NHL", emoji: "🏒", color: "#06b6d4" },
  { id: "soccer", label: "SOCCER", emoji: "⚽", color: "#22c55e" },
  { id: "mls", label: "MLS", emoji: "🥅", color: "#0ea5e9" },
  { id: "ufc", label: "UFC", emoji: "🥊", color: "#ef4444" },
  { id: "pga", label: "PGA", emoji: "⛳", color: "#10b981" },
  { id: "ncaaf", label: "NCAAF", emoji: "🏟️", color: "#a855f7" },
  { id: "ncaam", label: "NCAAM", emoji: "🏀", color: "#6366f1" },
  { id: "ncaaw", label: "NCAAW", emoji: "🏀", color: "#ec4899" },
  { id: "boxing", label: "BOXING", emoji: "🥋", color: "#f59e0b" },
];

const NAV_LINKS = [
  { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { name: "Projections", href: "/projections", icon: Users },
  { name: "Optimizer", href: "/optimizer", icon: Calculator },
  { name: "Backtesting", href: "/backtesting", icon: Activity },
  { name: "Billing", href: "/billing", icon: CreditCard },
  { name: "Admin", href: "/admin", icon: Settings },
];

function NavigationInner() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, isAuthenticated, isLoading, logout } = useAuth();

  const activeSport = searchParams.get("sport") || "nfl";

  // Hide navigation on landing page
  if (pathname === "/") return null;

  const handleSportClick = (sportId: string) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("sport", sportId);
    router.push(`/dashboard?${params.toString()}`);
  };

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  // Pages that don't need auth (auth pages themselves)
  const isAuthPage =
    pathname === "/login" || pathname === "/register";

  return (
    <div
      className="flex h-full w-64 flex-col border-r"
      style={{ background: "#0d1117", borderColor: "#30363d" }}
    >
      {/* Logo */}
      <div
        className="flex h-16 shrink-0 items-center gap-3 px-4 border-b"
        style={{ borderColor: "#30363d" }}
      >
        <Link href="/" className="flex items-center gap-2.5">
          <div
            className="w-8 h-8 rounded-xl flex items-center justify-center text-sm font-black shrink-0"
            style={{
              background: "linear-gradient(135deg, #00dc82, #00b368)",
            }}
          >
            S
          </div>
          <span
            className="text-sm font-black italic tracking-tight"
            style={{ color: "#00dc82" }}
          >
            SPORTBOOK ME
          </span>
        </Link>
      </div>

      {/* Sport Selector */}
      <div
        className="px-3 py-4 border-b"
        style={{ borderColor: "#30363d" }}
      >
        <p
          className="text-[9px] font-black uppercase tracking-widest mb-3"
          style={{ color: "#8b949e" }}
        >
          Select Sport
        </p>
        <div className="grid grid-cols-3 gap-1.5">
          {SPORTS.map((sport) => {
            const isActive = activeSport === sport.id;
            return (
              <button
                key={sport.id}
                onClick={() => handleSportClick(sport.id)}
                title={sport.label}
                className="flex flex-col items-center gap-1 py-2 px-1 rounded-xl transition-all duration-150 text-center"
                style={{
                  background: isActive ? `${sport.color}22` : "transparent",
                  border: isActive
                    ? `1px solid ${sport.color}55`
                    : "1px solid transparent",
                }}
              >
                <span className="text-base leading-none">{sport.emoji}</span>
                <span
                  className="text-[8px] font-black uppercase leading-none"
                  style={{
                    color: isActive ? sport.color : "#8b949e",
                  }}
                >
                  {sport.label}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Nav Links */}
      <nav className="flex-1 space-y-0.5 px-3 py-3 overflow-y-auto scroll-hide">
        {NAV_LINKS.map((link) => {
          const Icon = link.icon;
          const isActive = pathname === link.href;
          // Protect billing and optimizer — require auth
          const requiresAuth =
            link.href === "/optimizer" || link.href === "/billing";
          if (requiresAuth && !isAuthenticated) return null;

          return (
            <Link
              key={link.name}
              href={link.href}
              className={cn(
                "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-150",
                isActive
                  ? "text-[#0d1117] font-black"
                  : "text-[#8b949e] hover:text-white hover:bg-[#161b22]"
              )}
              style={
                isActive
                  ? {
                      background: "#00dc82",
                      boxShadow: "0 2px 12px rgba(0,220,130,0.35)",
                    }
                  : {}
              }
            >
              <Icon className="size-4 shrink-0" />
              {link.name}
            </Link>
          );
        })}
      </nav>

      {/* User / Auth Card */}
      <div
        className="p-3 border-t"
        style={{ borderColor: "#30363d" }}
      >
        {isLoading ? (
          <div
            className="flex items-center gap-3 rounded-xl p-3"
            style={{ border: "1px solid #30363d" }}
          >
            <div className="w-10 h-10 rounded-xl bg-[#21262d] animate-pulse" />
            <div className="flex-1 space-y-1.5">
              <div className="h-3 w-24 bg-[#21262d] rounded animate-pulse" />
              <div className="h-2 w-16 bg-[#21262d] rounded animate-pulse" />
            </div>
          </div>
        ) : isAuthenticated && user ? (
          <div
            className="flex items-center gap-3 rounded-xl p-3 transition-all"
            style={{ border: "1px solid #30363d" }}
          >
            <div
              className={cn(
                "w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
              )}
              style={{
                background:
                  user.plan === "Elite Stack"
                    ? "rgba(249,115,22,0.15)"
                    : "rgba(0,220,130,0.15)",
                color:
                  user.plan === "Elite Stack" ? "#f97316" : "#00dc82",
              }}
            >
              <Zap className="size-5 fill-current" />
            </div>
            <div className="flex-1 min-w-0">
              <span className="text-sm font-black text-white truncate block">
                {user.email}
              </span>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span
                  className="text-[9px] font-black uppercase tracking-widest"
                  style={{
                    color:
                      user.plan === "Elite Stack"
                        ? "#f97316"
                        : "#00dc82",
                  }}
                >
                  {user.plan}
                </span>
                <div
                  className="w-1.5 h-1.5 rounded-full"
                  style={{ background: "#00dc82" }}
                />
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="p-1.5 rounded-lg hover:bg-[#21262d] transition-colors"
              title="Sign out"
            >
              <LogOut className="size-4" style={{ color: "#8b949e" }} />
            </button>
          </div>
        ) : (
          <div className="flex gap-2">
            <Link
              href="/login"
              className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl text-xs font-black uppercase tracking-wider transition-all hover:opacity-90"
              style={{
                background: "#161b22",
                color: "#c9d1d9",
                border: "1px solid #30363d",
              }}
            >
              <LogIn className="size-3.5" />
              Sign In
            </Link>
            <Link
              href="/register"
              className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl text-xs font-black uppercase tracking-wider transition-all hover:opacity-90"
              style={{
                background: "#00dc82",
                color: "#0d1117",
                boxShadow: "0 2px 10px rgba(0,220,130,0.3)",
              }}
            >
              <UserPlus className="size-3.5" />
              Join
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}

export function Navigation() {
  return (
    <Suspense fallback={null}>
      <NavigationInner />
    </Suspense>
  );
}
