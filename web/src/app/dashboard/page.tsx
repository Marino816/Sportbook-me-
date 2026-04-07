"use client";

import { Activity, AlertTriangle, Calendar, CheckCircle2, Save, XCircle } from "lucide-react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { checkHealth, fetchProjections, fetchPerformanceStats } from "@/lib/api";

export default function DashboardPage() {
  const { data: isApiConnected, isLoading: isHealthLoading } = useQuery({
    queryKey: ['health'],
    queryFn: checkHealth,
    refetchInterval: 30000
  });

  const { data: perf } = useQuery({
    queryKey: ['performance'],
    queryFn: fetchPerformanceStats
  });

  const { data: projections } = useQuery({
    queryKey: ['projections', 1],
    queryFn: () => fetchProjections(1)
  });

  const apiStatus = isHealthLoading ? "Checking..." : isApiConnected ? "API Connected" : "API Offline";

  return (
    <div className="flex-1 overflow-y-auto p-8 h-full bg-background">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-foreground tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground mt-1">Welcome back. Here's your DFS overview for today.</p>
        </div>
        <div className="flex items-center gap-3">
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium border ${isApiConnected ? 'bg-green-500/10 text-green-500 border-green-500/20' : 'bg-red-500/10 text-red-500 border-red-500/20'}`}>
            {isApiConnected ? <CheckCircle2 className="size-4" /> : <XCircle className="size-4" />} {apiStatus}
          </div>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <<KpiCard title="Active Players in Model" value={projections?.data?.length || 0} icon={Calendar} trend="Data Fetched Live" /> trend="Data Fetched Live" />
        <KpiCard title="Projected Edge" value={perf?.total_roi || "0%"} icon={Activity} trend={perf?.ave_error ? `MAE: ${perf.ave_error}` : "Calculating..."} />
        <KpiCard title="Win Rate" value={perf?.win_rate || "0%"} icon={Save} trend="Historical performance" />
        <KpiCard title="Active Alerts" value="3" icon={AlertTriangle} trend="Critical injuries" destructive />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content - Slates */}
        <div className="lg:col-span-2 space-y-6">
          <div className="glass rounded-xl p-6 border border-border">
            <h2 className="text-xl font-bold mb-4">Today's Slates</h2>
            <div className="space-y-4">
              <SlateCard sport="NBA" time="7:00 PM EST" games={6} site="DraftKings" />
              <SlateCard sport="NBA" time="7:30 PM EST" games={4} site="FanDuel" />
              <SlateCard sport="MLB" time="1:05 PM EST" games={15} site="DraftKings" />
            </div>
            <div className="mt-4 pt-4 border-t border-border">
               <Link href="/optimizer" className="text-primary text-sm font-medium hover:underline flex items-center">
                 Go to Optimizer &rarr;
               </Link>
            </div>
          </div>
          
          <div className="glass rounded-xl p-6 border border-border h-64 flex flex-col items-center justify-center relative overflow-hidden">
             {/* Simple Line Chart Visualization */}
             <div className="absolute inset-0 opacity-10 flex items-end">
               <div className="w-full h-32 bg-primary/20 blur-xl translate-y-16" />
             </div>
             <Activity className="size-8 text-primary mb-3" />
             <h3 className="font-bold text-xl text-foreground">{perf?.total_roi || "+0.0%"} ROI</h3>
             <p className="text-sm text-balance text-center text-muted-foreground/70 max-w-sm mt-2">
               Your bankroll is up across the last 30 slates. {perf?.win_rate} win rate sustained.
             </p>
          </div>
        </div>

        {/* Sidebar - News Alerts */}
        <div className="space-y-6">
          <div className="glass rounded-xl p-6 border border-border flex flex-col h-full">
            <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
              <AlertTriangle className="size-5 text-amber-500" />
              Live News
            </h2>
            <div className="flex-1 space-y-4">
              <NewsItem time="10m ago" text="LeBron James (LAL) listed as QUESTIONABLE for tonight." impact="negative" />
              <NewsItem time="1h ago" text="Anthony Davis (LAL) upgraded to PROBABLE." impact="positive" />
              <NewsItem time="2h ago" text="Vegas line on LAL vs GSW moved to 238.5 (+2.0)." impact="neutral" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function KpiCard({ title, value, icon: Icon, trend, destructive }: any) {
  return (
    <div className="glass p-6 rounded-xl border border-border flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-muted-foreground">{title}</h3>
        <div className={`p-2 rounded-lg ${destructive ? 'bg-red-500/10 text-red-500' : 'bg-primary/10 text-primary'}`}>
          <Icon className="size-4" />
        </div>
      </div>
      <div className="text-3xl font-bold mb-1">{value}</div>
      <div className={`text-xs ${destructive ? 'text-red-400' : 'text-muted-foreground'}`}>{trend}</div>
    </div>
  );
}

function SlateCard({ sport, time, games, site }: any) {
  return (
    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between p-4 rounded-lg bg-secondary/50 border border-border hover:bg-secondary transition-colors cursor-pointer">
      <div className="flex items-center gap-4">
        <div className={`size-12 rounded-lg flex items-center justify-center font-bold text-lg ${sport === 'NBA' ? 'bg-orange-500/20 text-orange-500' : 'bg-blue-500/20 text-blue-500'}`}>
          {sport}
        </div>
        <div>
          <div className="font-bold text-lg">{site} Main Slate</div>
          <div className="text-sm text-muted-foreground">{time} • {games} Games</div>
        </div>
      </div>
      <button className="mt-3 sm:mt-0 px-4 py-2 bg-primary text-primary-foreground text-sm font-medium rounded-lg hover:bg-primary/90 transition-colors shadow-lg shadow-primary/20">
        Load Slate
      </button>
    </div>
  );
}

function NewsItem({ time, text, impact }: any) {
  return (
    <div className="flex gap-3 pb-3 border-b border-border/50 last:border-0 last:pb-0">
      <div className={`mt-1 size-2 rounded-full shrink-0 ${impact === 'negative' ? 'bg-red-500' : impact === 'positive' ? 'bg-green-500' : 'bg-blue-500'}`} />
      <div>
        <p className="text-sm text-foreground leading-snug">{text}</p>
        <span className="text-xs text-muted-foreground mt-1 block">{time}</span>
      </div>
    </div>
  );
}
