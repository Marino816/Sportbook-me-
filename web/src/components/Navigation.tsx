"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import {
  Home, MessageCircle, Flame, List, User, CreditCard,
  Settings, LogOut, UserPlus, LogIn,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { Suspense } from "react";

const NAV_LINKS = [
  { name: "Home", href: "/dashboard", icon: Home },
  { name: "AI", href: "/ai", icon: MessageCircle },
  { name: "Optimizer", href: "/optimizer", icon: Flame },
  { name: "Lineups", href: "/lineups", icon: List },
  { name: "Profile", href: "/profile", icon: User },
];

function NavigationInner() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, isAuthenticated, isLoading, logout } = useAuth();

  if (pathname === "/") return null;

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  const isAuthPage = pathname === "/login" || pathname === "/register";

  return (
    <div
      className="flex h-full w-64 flex-col border-r"
      style={{ background: "#0a0f24", borderColor: "#1e293b" }}
    >
      {/* Logo */}
      <div
        className="flex h-16 shrink-0 items-center justify-center px-4 border-b"
        style={{ borderColor: "#1e293b" }}
      >
        <Link href="/dashboard" className="flex items-center">
          <Image src="/logo.png" alt="SB ME DFS.AI" width={130} height={68} priority />
        </Link>
      </div>

      {/* Nav Links */}
      <nav className="flex-1 space-y-0.5 px-3 py-4 overflow-y-auto scroll-hide">
        {NAV_LINKS.map((link) => {
          const Icon = link.icon;
          const isActive = pathname === link.href;

          return (
            <Link
              key={link.name}
              href={link.href}
              className={cn(
                "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-150",
                isActive
                  ? "font-bold"
                  : "text-[#94a3b8] hover:text-white hover:bg-[#0a0f24]"
              )}
              style={
                isActive
                  ? {
                      background: "#c9a84c",
                      color: "#060b1a",
                      boxShadow: "0 2px 12px rgba(201,168,76,0.35)",
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
      <div className="p-3 border-t" style={{ borderColor: "#1e293b" }}>
        {isLoading ? (
          <div className="flex items-center gap-3 rounded-xl p-3" style={{ border: "1px solid #1e293b" }}>
            <div className="w-10 h-10 rounded-xl bg-[#1e293b] animate-pulse" />
            <div className="flex-1 space-y-1.5">
              <div className="h-3 w-24 bg-[#1e293b] rounded animate-pulse" />
              <div className="h-2 w-16 bg-[#1e293b] rounded animate-pulse" />
            </div>
          </div>
        ) : isAuthenticated && user ? (
          <div className="flex items-center gap-3 rounded-xl p-3" style={{ border: "1px solid #1e293b" }}>
            <div
              className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
              style={{ background: "rgba(201,168,76,0.15)", color: "#c9a84c" }}
            >
              <span className="text-sm font-black">{user.email?.[0]?.toUpperCase() || "U"}</span>
            </div>
            <div className="flex-1 min-w-0">
              <span className="text-sm font-bold text-white truncate block">{user.email}</span>
              <span className="text-[9px] font-black uppercase tracking-widest" style={{ color: "#c9a84c" }}>
                {user.plan || "Free"}
              </span>
            </div>
            <button onClick={handleLogout} className="p-1.5 rounded-lg hover:bg-[#1e293b] transition-colors" title="Sign out">
              <LogOut className="size-4" style={{ color: "#94a3b8" }} />
            </button>
          </div>
        ) : (
          <div className="flex gap-2">
            <Link href="/login" className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl text-xs font-bold uppercase tracking-wider transition-all"
              style={{ background: "#0a0f24", color: "#c9d1d9", border: "1px solid #1e293b" }}>
              <LogIn className="size-3.5" /> Sign In
            </Link>
            <Link href="/register" className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl text-xs font-bold uppercase tracking-wider"
              style={{ background: "#c9a84c", color: "#060b1a" }}>
              <UserPlus className="size-3.5" /> Join
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