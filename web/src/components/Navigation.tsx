"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { LayoutDashboard, Calculator, Activity, CreditCard, Settings, Zap, Users } from "lucide-react";
import { cn } from "@/lib/utils";
import { fetchSubscriptionStatus, type SubscriptionStatus } from "@/lib/api";
import { useEffect, useState } from "react";

const SPORTS = [
  { id: "nfl",    label: "NFL",    emoji: "🏈", color: "#d4ac0d" },
  { id: "nba",    label: "NBA",    emoji: "🏀", color: "#f97316" },
  { id: "mlb",    label: "MLB",    emoji: "⚾", color: "#3b82f6" },
  { id: "nhl",    label: "NHL",    emoji: "🏒", color: "#06b6d4" },
  { id: "soccer", label: "SOCCER", emoji: "⚽", color: "#22c55e" },
  { id: "mls",    label: "MLS",    emoji: "🥅", color: "#0ea5e9" },
  { id: "ufc",    label: "UFC",    emoji: "🥊", color: "#ef4444" },
  { id: "pga",    label: "PGA",    emoji: "⛳", color: "#10b981" },
  { id: "ncaaf",  label: "NCAAF",  emoji: "🏟️", color: "#a855f7" },
  { id: "ncaam",  label: "NCAAM",  emoji: "🏀", color: "#6366f1" },
  { id: "ncaaw",  label: "NCAAW",  emoji: "🏀", color: "#ec4899" },
  { id: "boxing", label: "BOXING", emoji: "🥋", color: "#f59e0b" },
];

const NAV_LINKS = [
  { name: "Dashboard",   href: "/dashboard",   icon: LayoutDashboard },
  { name: "Projections", href: "/projections",  icon: Users },
  { name: "Optimizer",   href: "/optimizer",    icon: Calculator },
  { name: "Backtesting", href: "/backtesting",  icon: Activity },
  { name: "Billing",     href: "/billing",      icon: CreditCard },
  { name: "Admin",       href: "/admin",        icon: Settings },
];

export function Navigation() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [sub, setSub] = useState<SubscriptionStatus | null>(null);

  const activeSport = searchParams.get("sport") || "nfl";

  useEffect(() => {
    async function load() {
      try {
        const res = await fetchSubscriptionStatus();
        setSub(res.data);
      } catch (e) {
        console.error("Nav status check failed", e);
      }
    }
    load();
  }, [pathname]);

  // Hide navigation on landing page
  if (pathname === "/") return null;

  const handleSportClick = (sportId: string) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("sport", sportId);
    router.push(`/dashboard?${params.toString()}`);
  };

  return (
    <div className="flex h-full w-64 flex-col border-r"
      style={{ background: "#0d1117", borderColor: "#30363d" }}>

      {/* ── LOGO ─────────────────────────────── */}
      <div className="flex h-16 shrink-0 items-center gap-3 px-4 border-b" style={{ borderColor: "#30363d" }}>
        <Link href="/" className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl flex items-center justify-center text-sm font-black shrink-0"
            style={{ background: "linear-gradient(135deg, #00dc82, #00b368)" }}>
            S
          </div>
          <span className="text-sm font-black italic tracking-tight" style={{ color: "#00dc82" }}>
            SPORTBOOK ME
          </span>
        </Link>
      </div>

      {/* ── SPORT SELECTOR ────────────────────── */}
      <div className="px-3 py-4 border-b" style={{ borderColor: "#30363d" }}>
        <p className="text-[9px] font-black uppercase tracking-widest mb-3" style={{ color: "#8b949e" }}>
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
                  border: isActive ? `1px solid ${sport.color}55` : "1px solid transparent",
                }}
              >
                <span className="text-base leading-none">{sport.emoji}</span>
                <span className="text-[8px] font-black uppercase leading-none"
                  style={{ color: isActive ? sport.color : "#8b949e" }}>
                  {sport.label}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* ── NAV LINKS ─────────────────────────── */}
      <nav className="flex-1 space-y-0.5 px-3 py-3 overflow-y-auto scroll-hide">
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
                  ? "text-[#0d1117] font-black"
                  : "text-[#8b949e] hover:text-white hover:bg-[#161b22]"
              )}
              style={isActive ? {
                background: "#00dc82",
                boxShadow: "0 2px 12px rgba(0,220,130,0.35)",
              } : {}}
            >
              <Icon className="size-4 shrink-0" />
              {link.name}
            </Link>
          );
        })}
      </nav>

      {/* ── USER / PLAN CARD ──────────────────── */}
      <div className="p-3 border-t" style={{ borderColor: "#30363d" }}>
        <Link href="/billing"
          className="flex items-center gap-3 rounded-xl p-3 transition-all hover:bg-[#161b22]"
          style={{ border: "1px solid #30363d" }}>
          <div className={cn(
            "w-10 h-10 rounded-xl flex items-center justify-center transition-transform hover:scale-110 shrink-0",
          )}
            style={{
              background: sub?.plan === "Elite Stack" ? "rgba(249,115,22,0.15)" : "rgba(0,220,130,0.15)",
              color: sub?.plan === "Elite Stack" ? "#f97316" : "#00dc82",
            }}>
            {sub?.plan === "Starter" ? <Users className="size-5" /> : <Zap className="size-5 fill-current" />}
          </div>
          <div className="flex-1 min-w-0">
            <span className="text-sm font-black text-white truncate block">shark@apexdfs.io</span>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className="text-[9px] font-black uppercase tracking-widest"
                style={{ color: sub?.plan === "Elite Stack" ? "#f97316" : "#00dc82" }}>
                {sub?.plan || "Starter"}
              </span>
              <div className="w-1.5 h-1.5 rounded-full"
                style={{ background: sub?.has_access ? "#00dc82" : "#6b7280" }} />
            </div>
          </div>
        </Link>
      </div>
    </div>
  );
}
