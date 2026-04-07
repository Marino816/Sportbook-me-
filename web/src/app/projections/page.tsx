"use client";

import { Filter, Search, Download } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { fetchProjections, type PlayerProjection } from "@/lib/api";

export default function ProjectionsPage() {
  const { data: projections, isLoading } = useQuery({
    queryKey: ['projections', 1],
    queryFn: () => fetchProjections(1)
  });

  return (
    <div className="flex-1 overflow-y-auto p-8 h-full bg-background flex flex-col">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-foreground tracking-tight">Projections</h1>
          <p className="text-muted-foreground mt-1">Machine-learning generated fantasy projections, updated every 5 minutes.</p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 bg-secondary text-foreground hover:bg-secondary/80 rounded-lg text-sm font-medium transition-colors border border-border">
          <Download className="size-4" /> Export CSV
        </button>
      </div>

      <div className="glass rounded-xl border border-border flex-1 flex flex-col overflow-hidden">
        {/* Filters Bar */}
        <div className="p-4 border-b border-border flex flex-wrap gap-4 items-center justify-between bg-card/80">
          <div className="flex items-center gap-4">
            <select className="bg-secondary text-foreground border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary">
              <option>DraftKings NBA</option>
              <option>FanDuel NBA</option>
              <option>DraftKings MLB</option>
            </select>
            <select className="bg-secondary text-foreground border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary">
              <option>All Positions</option>
              <option>PG</option>
              <option>SG</option>
              <option>SF</option>
            </select>
            <button className="flex items-center gap-2 px-3 py-2 bg-secondary text-muted-foreground hover:text-foreground rounded-lg border border-border text-sm">
              <Filter className="size-4" /> More Filters
            </button>
          </div>
          
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
            <input 
              type="text" 
              placeholder="Search players..." 
              className="bg-secondary/50 border border-border text-foreground rounded-lg pl-9 pr-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary w-64"
            />
          </div>
        </div>

        {/* Data Table */}
        <div className="overflow-x-auto flex-1">
          <table className="w-full text-sm text-left">
            <thead className="text-xs text-muted-foreground uppercase bg-secondary/30 sticky top-0">
              <tr>
                <th className="px-6 py-4 font-medium">Athlete</th>
                <th className="px-6 py-4 font-medium">Pos</th>
                <th className="px-6 py-4 font-medium">Salary</th>
                <th className="px-6 py-4 font-medium text-primary">Proj</th>
                <th className="px-6 py-4 font-medium">Ceil</th>
                <th className="px-6 py-4 font-medium">Floor</th>
                <th className="px-6 py-4 font-medium">Value</th>
                <th className="px-6 py-4 font-medium">Own %</th>
                <th className="px-6 py-4 font-medium">Leverage</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {isLoading ? (
                <tr>
                   <td colSpan={9} className="px-6 py-8 text-center text-muted-foreground">Loading exact projections...</td>
                </tr>
              ) : projections?.data?.map((p: PlayerProjection) => (
                <TableRow key={p.id} {...p} />
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function TableRow(p: PlayerProjection) {
  const isOptimal = p.value > 5.2;
  return (
    <tr className="hover:bg-secondary/20 transition-colors">
      <td className="px-6 py-4">
        <div className="flex flex-col">
          <span className="font-bold text-foreground">{p.name}</span>
          <span className="text-[10px] text-muted-foreground uppercase font-black">{p.team}</span>
        </div>
      </td>
      <td className="px-6 py-4 text-muted-foreground">{p.roster_position}</td>
      <td className="px-6 py-4 text-foreground font-medium">${p.salary.toLocaleString()}</td>
      <td className="px-6 py-4 font-bold text-primary">{p.projected_fp.toFixed(1)}</td>
      <td className="px-6 py-4 text-muted-foreground">{p.ceiling.toFixed(1)}</td>
      <td className="px-6 py-4 text-muted-foreground">{p.floor.toFixed(1)}</td>
      <td className="px-6 py-4">
        <span className={`px-2 py-1 rounded text-xs font-medium ${isOptimal ? 'bg-green-500/10 text-green-500' : 'text-foreground'}`}>
          {p.value?.toFixed(2)}x
        </span>
      </td>
      <td className="px-6 py-4 text-muted-foreground">{p.ownership.toFixed(1)}%</td>
      <td className="px-6 py-4">
        <span className={p.leverage > 0 ? 'text-green-500' : 'text-red-500'}>{p.leverage > 0 ? '+' : ''}{p.leverage.toFixed(1)}</span>
      </td>
    </tr>
  );
}
