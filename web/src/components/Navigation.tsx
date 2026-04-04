"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Users, Calculator, Activity, CreditCard, Settings, LogIn, Zap } from "lucide-react";
import { cn } from "@/lib/utils";
import { fetchSubscriptionStatus, type SubscriptionStatus } from "@/lib/api";
import { useEffect, useState } from "react";

const links = [
  { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { name: "Projections", href: "/projections", icon: Users },
  { name: "Optimizer", href: "/optimizer", icon: Calculator },
  { name: "Backtesting", href: "/backtesting", icon: Activity },
  { name: "Billing", href: "/billing", icon: CreditCard },
  { name: "Admin", href: "/admin", icon: Settings },
];

export function Navigation() {
  const pathname = usePathname();
  const [sub, setSub] = useState<SubscriptionStatus | null>(null);

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

  return (
    <div className="flex h-full w-64 flex-col glass border-r border-border">
      <div className="flex h-16 shrink-0 items-center px-6">
        <Link href="/" className="flex items-center gap-2">
          <h1 className="text-xl font-bold tracking-tight text-white">SPORTSBOOK <span className="text-neon-green">ME DFS AI</span></h1>
        </Link>
      </div>

      <nav className="flex-1 space-y-1 px-4 py-4">
        {links.map((link) => {
          const Icon = link.icon;
          const isActive = pathname === link.href;
          return (
            <Link
              key={link.name}
              href={link.href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200",
                isActive 
                  ? "bg-primary text-primary-foreground shadow-md shadow-primary/20" 
                  : "text-muted-foreground hover:bg-secondary hover:text-foreground"
              )}
            >
              <Icon className="size-5" />
              {link.name}
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t border-border mt-auto">
        <Link href="/billing" className="flex items-center gap-3 rounded-xl bg-[#0F1115] border border-white/5 p-3 hover:bg-white/5 transition-colors group">
          <div className={cn(
            "size-10 rounded-lg flex items-center justify-center transition-transform group-hover:scale-110",
            sub?.plan === "Elite Stack" ? "bg-orange-500/10 text-orange-500" : "bg-primary/10 text-primary"
          )}>
            {sub?.plan === "Starter" ? <Users className="size-5" /> : <Zap className="size-5 fill-current" />}
          </div>
          <div className="flex-1 min-w-0">
            <span className="text-sm font-black text-white italic tracking-tight truncate block">shark@apexdfs.io</span>
            <div className="flex items-center gap-1.5">
               <span className={cn(
                 "text-[9px] font-black uppercase italic tracking-widest",
                 sub?.plan === "Elite Stack" ? "text-orange-500" : "text-primary"
               )}>
                 {sub?.plan || "Starter"}
               </span>
               <div className={cn(
                 "size-1 rounded-full",
                 sub?.has_access ? "bg-green-500" : "bg-slate-500"
               )} />
            </div>
          </div>
        </Link>
      </div>
    </div>
  );
}
