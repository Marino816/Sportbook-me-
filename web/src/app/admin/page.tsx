'use client';

import React from 'react';
import { 
  ArrowUpRight, 
  ArrowDownRight, 
  Search, 
  Bell, 
  HelpCircle, 
  ExternalLink,
  Users,
  CreditCard,
  TrendingDown,
  Zap,
  TrendingUp,
  Activity,
  CheckCircle2,
  Settings,
  RefreshCw
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { 
  fetchAdminSummary, 
  fetchRevenueTrends, 
  fetchAdminEvents, 
  fetchPlanDistribution,
  fetchSystemStatus,
  triggerManualSync,
  type SystemStatus,
  type ApiResponse
} from '@/lib/api';
import { ErrorState } from '@/components/States';

export default function AdminDashboard() {
  const [summary, setSummary] = React.useState<any>(null);
  const [trends, setTrends] = React.useState<number[]>([]);
  const [events, setEvents] = React.useState<any[]>([]);
  const [dist, setDist] = React.useState<any>(null);
  const [health, setHealth] = React.useState<SystemStatus[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [syncing, setSyncing] = React.useState(false);

  const loadData = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, t, e, d, h] = await Promise.all([
        fetchAdminSummary(),
        fetchRevenueTrends(),
        fetchAdminEvents(),
        fetchPlanDistribution(),
        fetchSystemStatus()
      ]);
      setSummary(s.data);
      setTrends(t.data);
      setEvents(e.data);
      setDist(d.data);
      setHealth(h.data);
    } catch (err: any) {
      setError(err.message || "Failed to initialize diagnostic protocol.");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    loadData();
  }, [loadData]);

  const handleManualSync = async () => {
    setSyncing(true);
    try {
      await triggerManualSync();
      await loadData();
    } catch (e) {
      console.error("Manual sync failed", e);
    } finally {
      setSyncing(false);
    }
  };

  if (loading) return (
    <div className="flex-1 flex flex-col items-center justify-center bg-[#0F1115]">
       <div className="size-16 border-2 border-t-[#00FF9D] border-white/5 rounded-full animate-spin mb-6" />
       <p className="text-[#00FF9D] font-black italic tracking-widest animate-pulse">ESTABLISHING SECURE CONNECTION...</p>
    </div>
  );

  if (error) return (
    <div className="flex-1 flex bg-[#0F1115]">
       <ErrorState message={error} onRetry={loadData} />
    </div>
  );
  return (
    <div className="flex-1 flex flex-col h-full bg-[#0F1115] text-white">
      {/* Top Header */}
      <header className="h-20 border-b border-[#1E2028] px-8 flex items-center justify-between">
        <div className="flex items-center gap-8 flex-1">
          <h1 className="text-xl font-black italic tracking-tight">Apex DFS AI</h1>
          <div className="relative max-w-md w-full">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-[#A1A1A1]" />
            <input 
              type="text" 
              placeholder="Search billing records..." 
              className="w-full bg-[#1A1C23] border border-[#272A35] rounded-lg py-2 pl-10 pr-4 text-sm focus:outline-none focus:border-[#00FF9D] transition-all"
            />
          </div>
        </div>
        <div className="flex items-center gap-6">
          <button className="text-[#A1A1A1] hover:text-white"><Bell className="size-5" /></button>
          <button className="text-[#A1A1A1] hover:text-white"><Settings className="size-5" /></button>
          <button className="text-[#A1A1A1] hover:text-white"><HelpCircle className="size-5" /></button>
          <div className="flex items-center gap-3 pl-6 border-l border-[#1E2028]">
            <div className="text-right">
              <p className="text-[10px] font-black text-[#00FF9D] tracking-widest uppercase">ADMIN_01</p>
              <p className="text-[10px] font-bold text-[#A1A1A1] uppercase">SYSTEM SUPERUSER</p>
            </div>
            <div className="size-10 rounded-full bg-[#272A35] border border-white/10" />
          </div>
        </div>
      </header>

      {/* Dashboard Body */}
      <div className="p-8 space-y-8 overflow-y-auto">
        {/* KPI Row */}
        <div className="grid grid-cols-4 gap-6">
          <KPICard 
            label="MONTHLY RECURRING REVENUE" 
            value={summary?.mrr || "$0"} 
            trend={summary?.mrr_trend || "+0.0%"} 
            icon={<CreditCard className="size-5 text-[#00FF9D]" />}
            color="primary"
          />
          <KPICard 
            label="ACTIVE SUBSCRIBERS" 
            value={summary?.active_subscribers || "0"} 
            trend={summary?.subs_trend || "+0 new"} 
            icon={<Users className="size-5 text-[#B983FF]" />}
            color="purple"
          />
          <KPICard 
            label="CHURN RATE" 
            value={summary?.churn_rate || "0.0%"} 
            trend="-0.0% retention stable" 
            icon={<TrendingDown className="size-5 text-[#FF6363]" />}
            color="rose"
            isInverse
          />
          <KPICard 
            label="TRIAL CONVERSIONS" 
            value={summary?.trial_conversions || "0%"} 
            trend="+0% optimization" 
            icon={<Zap className="size-5 text-[#00FF99]" />}
            color="primary"
          />
        </div>

        {/* Middle Section: Trends & Plan Distribution */}
        <div className="grid grid-cols-3 gap-8">
          <div className="col-span-2 bg-[#171920] border border-[#272A35] rounded-2xl p-8 flex flex-col">
            <div className="flex items-center justify-between mb-8">
              <div>
                <h2 className="text-xl font-bold">Revenue Trends</h2>
                <p className="text-xs text-[#A1A1A1] mt-1">Growth performance over the last 30 days</p>
              </div>
              <div className="flex bg-[#0F1115] border border-[#272A35] p-1 rounded-lg">
                <button className="px-4 py-1 text-[10px] font-black text-[#A1A1A1]">7D</button>
                <button className="px-4 py-1 text-[10px] font-black text-white bg-[#00FF9D]/10 rounded-md">30D</button>
                <button className="px-4 py-1 text-[10px] font-black text-[#A1A1A1]">ALL</button>
              </div>
            </div>
            
            {/* Simple Bar Chart Visualization (using CSS) */}
            <div className="flex-1 flex items-end justify-between gap-4 h-64 px-4 pb-2">
              {(trends.length > 0 ? trends : [40, 55, 45, 60, 75, 50, 65, 80, 70, 95, 120, 150]).map((h, i) => (
                <div 
                  key={i} 
                  className={cn(
                    "flex-1 rounded-t-sm transition-all duration-500",
                    (i === trends.length - 1 || i === 11) ? "bg-[#00FF9D]" : "bg-[#00FF9D]/30"
                  )} 
                  style={{ height: `${h}px` }} 
                />
              ))}
            </div>
          </div>

          <div className="bg-[#171920] border border-[#272A35] rounded-2xl p-8 flex flex-col">
            <h2 className="text-xl font-bold mb-8">Plan Distribution</h2>
            <div className="space-y-8 flex-1">
              <ProgressRow label="Pro Arena" value={dist?.["Pro Arena"] || 55} color="primary" />
              <ProgressRow label="Elite Stack" value={dist?.["Elite Stack"] || 30} color="purple" />
              <ProgressRow label="Starter" value={dist?.["Starter"] || 15} color="text" />
            </div>
            
            <div className="mt-8 p-6 bg-[#00FF9D]/5 border border-[#00FF9D]/10 rounded-xl flex items-center gap-4">
              <div className="size-10 bg-[#00FF9D]/10 rounded flex items-center justify-center">
                <TrendingUp className="size-5 text-[#00FF9D]" />
              </div>
              <div>
                <p className="text-[10px] font-black text-[#00FF9D] uppercase">GROWTH ENGINE</p>
                <p className="text-xs font-medium text-white/80">Elite Stack up 4% this week</p>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom Section: Recent Events & System Health */}
        <div className="grid grid-cols-3 gap-8">
          <div className="col-span-2 bg-[#171920] border border-[#272A35] rounded-2xl overflow-hidden">
             <div className="p-8 flex items-center justify-between border-b border-[#272A35]">
               <div>
                 <h2 className="text-xl font-bold">Recent Subscription Events</h2>
                 <p className="text-xs text-[#A1A1A1] mt-1">Real-time billing activity feed</p>
               </div>
               <button className="flex items-center gap-2 text-[#00FF9D] text-xs font-bold hover:underline">
                 View Full Audit Log <ExternalLink className="size-3" />
               </button>
             </div>
             <table className="w-full text-left">
               <thead className="bg-[#0F1115] text-[10px] font-black text-[#A1A1A1] uppercase tracking-widest">
                 <tr>
                   <th className="px-8 py-4">EVENT TYPE</th>
                   <th className="px-8 py-4">SUBSCRIBER</th>
                   <th className="px-8 py-4">STATUS</th>
                   <th className="px-8 py-4">AMOUNT</th>
                   <th className="px-8 py-4">TIMESTAMP</th>
                 </tr>
               </thead>
               <tbody className="divide-y divide-white/5">
                 {events.map((event, i) => (
                   <EventRow 
                     key={i}
                     type={event.type} 
                     user={event.user} 
                     email={event.email} 
                     plan={event.plan} 
                     amount={event.amount} 
                     time={event.time} 
                     isWarning={event.plan === "RETRIABLE"}
                     icon={event.type === "New Signup" ? <Activity className="size-4 text-[#00FF9D]" /> : <RefreshCcw className="size-4 text-[#00FF9D]" />}
                   />
                 ))}
               </tbody>
             </table>
          </div>

          <div className="space-y-8">
            {/* Launch Readiness Card */}
            <div className="bg-[#171920] border border-[#00FF9D]/20 rounded-2xl p-8 relative overflow-hidden group">
               <div className="absolute -right-4 -top-4 size-32 bg-[#00FF9D]/5 rounded-full blur-3xl group-hover:bg-[#00FF9D]/10 transition-colors" />
               <h2 className="text-xl font-bold mb-6 flex items-center gap-2">
                 <Zap className="size-5 text-[#00FF9D]" /> Launch Readiness
               </h2>
               <div className="space-y-4 relative z-10">
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-slate-500 font-bold uppercase tracking-tighter">Database Node</span>
                    <span className="bg-green-500/10 text-green-500 px-2 py-0.5 rounded font-black italic">CONNECTED_STABLE</span>
                  </div>
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-slate-500 font-bold uppercase tracking-tighter">Worker Threads</span>
                    <span className="text-white font-black">4 ACTIVE</span>
                  </div>
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-slate-500 font-bold uppercase tracking-tighter">SSL Certificate</span>
                    <span className="text-primary font-black uppercase">VALID_PROD</span>
                  </div>
                  <div className="mt-6 pt-6 border-t border-white/5 space-y-3">
                     <button className="w-full py-2.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-[10px] font-black uppercase italic tracking-widest transition-colors flex items-center justify-center gap-2">
                        <Activity className="size-3 text-[#00FF9D]" /> Run Webhook Test
                     </button>
                     <p className="text-[9px] text-slate-500 text-center italic">Verify Stripe-to-Backend handshake</p>
                  </div>
               </div>
            </div>

            {/* System Health Card */}
            <div className="bg-[#171920] border border-[#272A35] rounded-2xl p-8">
               <div className="flex items-center justify-between mb-8">
                 <h2 className="text-xl font-bold">System Health</h2>
                 <button 
                  onClick={handleManualSync}
                  disabled={syncing}
                  className={cn(
                    "p-2 bg-[#00FF9D]/10 border border-[#00FF9D]/20 rounded-lg group transition-all",
                    syncing && "opacity-50 cursor-not-allowed"
                  )}
                 >
                   <RefreshCcw className={cn("size-4 text-[#00FF9D]", syncing && "animate-spin")} />
                 </button>
               </div>
               
               <div className="space-y-6">
                 {health.map((h, i) => (
                   <div key={i} className="flex gap-4">
                     <div className={cn("size-10 rounded-lg flex items-center justify-center", h.is_healthy ? "bg-green-500/10" : "bg-rose-500/10")}>
                        <CheckCircle2 className={cn("size-5", h.is_healthy ? "text-green-500" : "text-rose-500")} />
                     </div>
                     <div className="flex-1">
                        <div className="flex justify-between items-start">
                          <p className="text-xs font-black uppercase italic tracking-tighter">{h.provider_name}</p>
                          <span className="text-[10px] text-slate-500">{new Date(h.last_sync_time).toLocaleTimeString()}</span>
                        </div>
                        <p className="text-[11px] text-slate-400 mt-1">{h.last_sync_result}</p>
                        <div className="mt-2 flex items-center gap-2">
                          <span className={cn(
                            "px-2 py-0.5 rounded text-[8px] font-black uppercase",
                            h.data_source_mode === 'live' ? "bg-green-500/10 text-green-500" : "bg-amber-500/10 text-amber-500"
                          )}>
                            {h.data_source_mode}
                          </span>
                        </div>
                     </div>
                   </div>
                 ))}
               </div>
            </div>

            {/* Diagnostics Card */}
            <div className="bg-[#171920] border border-[#272A35] rounded-2xl p-8 relative overflow-hidden">
               <div className="absolute top-0 right-0 p-4 opacity-5">
                 <Settings className="size-24" />
               </div>
               <h2 className="text-xl font-bold mb-6">Diagnostics</h2>
               <div className="space-y-4">
                  <DiagRow label="Backend Host" val={process.env.NEXT_PUBLIC_API_URL || 'localhost:8000'} />
                  <DiagRow label="Environment" val={process.env.NODE_ENV || 'development'} />
                  <DiagRow label="Protocol" val="REST / HTTP 1.1 SSL" />
                  <DiagRow label="LAN Connect" val="Enabled" color="primary" />
                  <DiagRow label="App Version" val="1.2.0-PROD" />
               </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function BarChart3Icon({ className }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 3v18h18"/><path d="M7 16h3"/><path d="M7 11h11"/><path d="M7 6h6"/></svg>
  );
}

function RefreshCcw({ className }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 16h5v5"/></svg>
  );
}

function KPICard({ label, value, trend, icon, color, isInverse }: any) {
  const colors: Record<string, string> = {
    primary: 'border-[#00FF9D] bg-[#00FF9D]/10',
    purple: 'border-[#B983FF] bg-[#B983FF]/10',
    rose: 'border-[#FF6363] bg-[#FF6363]/10',
  };

  return (
    <div className="bg-[#171920] border border-[#272A35] rounded-2xl p-6 flex flex-col h-32 relative overflow-hidden">
      <div className={cn("absolute left-0 top-0 bottom-0 w-[4px]", color === 'primary' ? 'bg-[#00FF9D]' : color === 'purple' ? 'bg-[#B983FF]' : 'bg-[#FF6363]')} />
      <div className="flex items-center justify-between mb-4">
        <span className="text-[10px] font-bold text-[#A1A1A1] uppercase tracking-wider">{label}</span>
        <div className={cn("p-2 rounded-lg", colors[color] || 'bg-[#272A35]')}>
          {icon}
        </div>
      </div>
      <div className="mt-auto">
        <h3 className="text-2xl font-black text-white">{value}</h3>
        <p className={cn("text-[10px] font-medium mt-1 uppercase", isInverse ? 'text-[#FF6363]' : 'text-[#00FF9D]')}>
          {trend}
        </p>
      </div>
    </div>
  );
}

function ProgressRow({ label, value, color }: any) {
  return (
    <div className="space-y-3">
      <div className="flex justify-between items-center text-xs font-bold uppercase tracking-wider">
        <span>{label}</span>
        <span className={cn(color === 'primary' ? 'text-[#00FF9D]' : color === 'purple' ? 'text-[#B983FF]' : 'text-white')}>{value}%</span>
      </div>
      <div className="h-2 bg-[#0F1115] rounded-full overflow-hidden border border-[#272A35]">
        <div 
          className={cn("h-full rounded-full transition-all duration-300", color === 'primary' ? 'bg-[#00FF9D]' : color === 'purple' ? 'bg-[#B983FF]' : 'bg-white')} 
          style={{ width: `${value}%` }} 
        />
      </div>
    </div>
  );
}

function EventRow({ type, user, email, plan, amount, time, icon, isWarning }: any) {
  return (
    <tr className="group hover:bg-white/5 transition-colors">
      <td className="px-8 py-5">
        <div className="flex items-center gap-3">
          <div className="size-10 bg-[#0F1115] border border-[#272A35] rounded-lg flex items-center justify-center group-hover:scale-110 transition-transform">
            {icon}
          </div>
          <span className="text-xs font-bold text-[#A1A1A1] uppercase">{type}</span>
        </div>
      </td>
      <td className="px-8 py-5">
        <div className="flex flex-col">
          <span className="text-sm font-black text-white">{user}</span>
          <span className="text-xs text-[#A1A1A1]">{email}</span>
        </div>
      </td>
      <td className="px-8 py-5">
        <span className={cn(
          "px-3 py-1 text-[10px] font-black rounded-md uppercase",
          isWarning ? "bg-[#FF6363]/10 text-[#FF6363]" : "bg-[#00FF9D]/10 text-[#00FF9D]"
        )}>
          {plan}
        </span>
      </td>
      <td className="px-8 py-5 text-sm font-black text-white">{amount}</td>
      <td className="px-8 py-5 text-xs text-[#A1A1A1]">{time}</td>
    </tr>
  );
}

function DiagRow({ label, val, color }: any) {
  return (
    <div className="flex justify-between items-center text-xs">
      <span className="text-slate-500 font-bold uppercase tracking-tighter">{label}</span>
      <span className={cn("font-black tracking-tight", color === 'primary' ? 'text-[#00FF9D]' : 'text-white')}>
        {val}
      </span>
    </div>
  );
}
