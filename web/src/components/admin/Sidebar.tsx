'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { 
  BarChart3, 
  LayoutDashboard, 
  Users, 
  Target, 
  CreditCard, 
  Activity, 
  FileText, 
  Zap, 
  Settings, 
  Search, 
  Bell, 
  HelpCircle, 
  LogOut,
  RefreshCcw
} from 'lucide-react';
import { cn } from '@/lib/utils';

const sidebarItems = [
  { name: 'DASHBOARD', icon: LayoutDashboard, href: '/admin' },
  { name: 'PROJECTIONS', icon: BarChart3, href: '/admin/projections' },
  { name: 'OPTIMIZER', icon: Zap, href: '/admin/optimizer' },
  { name: 'BILLING', icon: CreditCard, href: '/admin/billing' },
  { name: 'USERS', icon: Users, href: '/admin/users' },
];

const secondaryItems = [
  { name: 'SUPPORT', icon: HelpCircle, href: '/admin/support' },
  { name: 'LOGS', icon: FileText, href: '/admin/logs' },
];

export function AdminSidebar() {
  const pathname = usePathname();

  return (
    <div className="w-64 h-screen bg-[#0F1115] border-r border-[#1E2028] flex flex-col fixed left-0 top-0 z-50">
      {/* Logo */}
      <div className="p-6 flex items-center gap-3">
        <div className="size-8 bg-[#00FF9D] rounded flex items-center justify-center">
          <Zap className="size-5 text-black fill-black" />
        </div>
        <div>
          <h2 className="text-white font-black text-lg italic tracking-tight uppercase leading-none">APEX ENGINE</h2>
          <span className="text-[10px] text-[#A1A1A1] font-bold tracking-widest block mt-1 uppercase">ADMIN TERMINAL</span>
        </div>
      </div>

      <nav className="flex-1 px-4 py-8 space-y-8 overflow-y-auto">
        {/* Main Nav */}
        <div className="space-y-1">
          {sidebarItems.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.name}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-bold transition-all duration-200 group",
                  isActive 
                    ? "bg-[#00FF9D]/10 text-[#00FF9D] border border-[#00FF9D]/20 shadow-[0_0_15px_rgba(0,255,157,0.1)]" 
                    : "text-[#A1A1A1] hover:text-white hover:bg-white/5"
                )}
              >
                <item.icon className={cn("size-5", isActive ? "text-[#00FF9D]" : "text-[#A1A1A1] group-hover:text-white")} />
                {item.name}
              </Link>
            );
          })}
        </div>

        {/* Action Button */}
        <div className="px-4">
          <button className="w-full h-12 bg-[#00FF9D] hover:bg-[#00E68E] text-black font-black text-sm rounded-lg flex items-center justify-center gap-2 transition-transform active:scale-95 shadow-[0_0_20px_rgba(0,255,157,0.3)]">
             <RefreshCcw className="size-4" strokeWidth={3} />
             RUN GLOBAL SYNC
          </button>
        </div>

        {/* Secondary Nav */}
        <div className="space-y-1 pt-8 border-t border-white/5">
          {secondaryItems.map((item) => (
            <Link
              key={item.name}
              href={item.href}
              className="flex items-center gap-3 px-4 py-2 rounded-lg text-xs font-bold text-[#A1A1A1] hover:text-white hover:bg-white/5 transition-all"
            >
              <item.icon className="size-4" />
              {item.name}
            </Link>
          ))}
        </div>
      </nav>

      <div className="p-4 border-t border-white/5">
        <button className="w-full flex items-center gap-3 px-4 py-2 rounded-lg text-xs font-bold text-red-400 hover:bg-red-500/10 transition-all">
          <LogOut className="size-4" />
          LOGOUT SYSTEM
        </button>
      </div>
    </div>
  );
}
