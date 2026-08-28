"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import {
  Home, MessageCircle, Flame, List, User, LogOut, LogIn, UserPlus,
  Database, BarChart3,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { Suspense } from "react";

const TABS = [
  { name: "Home", href: "/dashboard", icon: Home },
  { name: "Data Hub", href: "/data-hub", icon: Database },
  { name: "Optimizer", href: "/optimizer", icon: Flame },
  { name: "Market Tools", href: "/market-tools", icon: BarChart3 },
  { name: "AI", href: "/ai", icon: MessageCircle },
  { name: "Lineups", href: "/lineups", icon: List },
  { name: "Profile", href: "/profile", icon: User },
];

function TopNavInner() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, isAuthenticated, logout } = useAuth();

  if (pathname === "/") return null;
  const isAuthPage = pathname === "/login" || pathname === "/register";

  return (
    <header style={{
      position: "sticky", top: 0, zIndex: 50,
      background: "rgba(10,15,36,0.92)", backdropFilter: "blur(16px)",
      borderBottom: "1px solid #1e293b",
    }}>
      <div style={{ maxWidth: 1280, margin: "0 auto", padding: "0 24px", display: "flex", alignItems: "center", height: 64 }}>
        {/* Logo */}
        <Link href="/dashboard" style={{ flexShrink: 0, marginRight: 32 }}>
          <Image src="/logo.png" alt="SB ME DFS.AI" width={110} height={58} priority />
        </Link>

        {/* Tabs */}
        <nav style={{ display: "flex", gap: 4, flex: 1, overflowX: "auto", flexWrap: "wrap" }}>
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = pathname === tab.href;
            return (
              <Link key={tab.name} href={tab.href} style={{
                display: "flex", alignItems: "center", gap: 6,
                padding: "8px 16px", borderRadius: 12, fontSize: 13,
                fontWeight: isActive ? 700 : 500,
                color: isActive ? "#c9a84c" : "#94a3b8",
                background: isActive ? "rgba(201,168,76,0.1)" : "transparent",
                border: isActive ? "1px solid rgba(201,168,76,0.3)" : "1px solid transparent",
                textDecoration: "none", transition: "all 0.15s",
              }}>
                <Icon size={16} />
                {tab.name}
              </Link>
            );
          })}
        </nav>

        {/* Auth */}
        <div style={{ flexShrink: 0 }}>
          {isAuthenticated && user ? (
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <span style={{ fontSize: 13, color: "#c9a84c", fontWeight: 600 }}>{user.email}</span>
              <button onClick={() => { logout(); router.push("/login"); }}
                style={{
                  background: "transparent", border: "1px solid #1e293b", borderRadius: 10,
                  padding: "8px 14px", color: "#94a3b8", cursor: "pointer", fontWeight: 600, fontSize: 12,
                }}>
                <LogOut size={14} />
              </button>
            </div>
          ) : isAuthPage ? null : (
            <div style={{ display: "flex", gap: 8 }}>
              <Link href="/login" style={{
                padding: "8px 16px", borderRadius: 10, fontSize: 13, fontWeight: 600,
                color: "#94a3b8", border: "1px solid #1e293b", textDecoration: "none",
              }}>
                <LogIn size={14} style={{ display: "inline", marginRight: 4 }} /> Sign In
              </Link>
              <Link href="/register" style={{
                padding: "8px 16px", borderRadius: 10, fontSize: 13, fontWeight: 600,
                background: "#c9a84c", color: "#060b1a", textDecoration: "none",
              }}>
                <UserPlus size={14} style={{ display: "inline", marginRight: 4 }} /> Join
              </Link>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

export function TopNav() {
  return (
    <Suspense fallback={null}>
      <TopNavInner />
    </Suspense>
  );
}