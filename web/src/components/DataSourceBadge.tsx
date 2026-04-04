"use client";

import React, { useEffect, useState } from 'react';
import { Database, ShieldCheck, AlertCircle, Info } from 'lucide-react';
import { cn } from '@/lib/utils';
import { fetchSystemStatus, type SystemStatus } from '@/lib/api';

export function DataSourceBadge() {
  const [status, setStatus] = useState<SystemStatus | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetchSystemStatus();
        if (res.data && res.data.length > 0) {
          setStatus(res.data[0]);
        }
      } catch (e) {
        console.error("Health check failed", e);
      }
    }
    load();
    const interval = setInterval(load, 60000); // 1 minute poll
    return () => clearInterval(interval);
  }, []);

  if (!status) return null;

  const mode = status.data_source_mode || 'live';
  
  return (
    <div className="fixed bottom-6 right-6 z-50 flex items-center gap-3">
      <div className={cn(
        "flex items-center gap-2 px-3 py-1.5 rounded-full border shadow-2xl backdrop-blur-md transition-all duration-500",
        mode === 'live' ? "bg-green-500/10 border-green-500/20 text-green-500" :
        mode === 'cached' ? "bg-amber-500/10 border-amber-500/20 text-amber-500" :
        "bg-rose-500/10 border-rose-500/20 text-rose-500"
      )}>
        <div className={cn(
          "size-1.5 rounded-full animate-pulse",
          mode === 'live' ? "bg-green-500" : mode === 'cached' ? "bg-amber-500" : "bg-rose-500"
        )} />
        <span className="text-[10px] font-black tracking-widest uppercase italic">
          {mode === 'live' ? "Live System" : mode === 'cached' ? "Cached" : "Demo Mode"}
        </span>
        
        <div className="group relative">
          <Info className="size-3 cursor-help opacity-50" />
          <div className="absolute bottom-full right-0 mb-3 w-64 p-3 bg-[#171920] border border-[#272A35] rounded-xl opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity shadow-2xl text-[11px] leading-relaxed text-slate-400">
             <div className="font-bold text-white mb-1 uppercase tracking-tighter italic">Data Integrity Report</div>
             <p>Source: {status.provider_name}</p>
             <p>Last Sync: {new Date(status.last_sync_time).toLocaleTimeString()}</p>
             <p className="mt-2 text-primary font-bold italic tracking-tighter">{status.last_sync_result}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
