"use client";

import { useState, useEffect } from "react";
import { ChevronDown, ChevronUp, History } from "lucide-react";

/**
 * Canonical Player Last-5 Game History component.
 *
 * ONE shared implementation used by Data Hub, Optimizer, Player Props, and
 * Parlay. It fetches provider-supplied historical player statistics through
 * the canonical SGO player-stats endpoint and, when that data is available,
 * renders previous completed games with platform fantasy scoring.
 *
 * The current SportsGameOdds subscription tier does NOT expose historical
 * player statistics (GET /sgo/players/{id}/stats returns 404), so the
 * component truthfully renders N/A rather than fabricating previous-game
 * lines from current projections.
 */

const navy = "#060b1a";
const gold = "#c9a84c";
const border = "#1e293b";
const textMuted = "#64748b";
const textSecondary = "#94a3b8";

export interface PlayerHistoryGame {
  date: string;
  opponent: string;
  result: string;
  fantasy_points: number | null; // DK or FD scored, else null
  stats: Record<string, string | number>;
}

export interface PlayerHistory {
  available: boolean;
  reason?: string;
  games: PlayerHistoryGame[];
}

// Platform fantasy scoring is applied server-side when stats are sufficient;
// the component only displays what the canonical history service returns.
export async function fetchPlayerHistory(playerId: string, platform: string): Promise<PlayerHistory> {
  const base = (typeof process !== "undefined" ? process.env.NEXT_PUBLIC_API_URL : undefined) || "https://sportbook-me-production.up.railway.app";
  const token = (typeof window !== "undefined" && localStorage.getItem("sbme_dfs_token")) || "";
  try {
    const res = await fetch(`${base}/api/sgo/players/${encodeURIComponent(playerId)}/stats?platform=${platform}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) {
      return { available: false, reason: res.status === 404 ? "Historical player stats unavailable on current SportsGameOdds subscription." : `HTTP ${res.status}`, games: [] };
    }
    const json = await res.json();
    const games = json?.data?.games ?? json?.games ?? [];
    return { available: Array.isArray(games) && games.length > 0, games: Array.isArray(games) ? games.slice(0, 5) : [] };
  } catch {
    return { available: false, reason: "Historical stats fetch failed.", games: [] };
  }
}

export function LastFive({ player, platform = "draftkings" }: { player: { name?: string; player_id?: string; id?: string } | null | undefined; platform?: string }) {
  const [open, setOpen] = useState(false);
  const [history, setHistory] = useState<PlayerHistory | null>(null);
  const [loading, setLoading] = useState(false);
  const pid = player?.player_id || player?.id || "";

  useEffect(() => {
    if (!open || !pid) return;
    let cancelled = false;
    setLoading(true);
    fetchPlayerHistory(pid, platform).then((h) => { if (!cancelled) { setHistory(h); setLoading(false); } });
    return () => { cancelled = true; };
  }, [open, pid, platform]);

  return (
    <div style={{ marginTop: 6 }}>
      <button onClick={() => setOpen((o) => !o)}
        style={{ display: "inline-flex", alignItems: "center", gap: 4, padding: "3px 8px", borderRadius: 6, fontSize: 11, fontWeight: 600, background: open ? `${gold}15` : "transparent", border: `1px solid ${open ? gold : border}`, color: open ? gold : textMuted, cursor: "pointer" }}>
        <History size={12} />
        Last 5
        {open ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
      </button>
      {open && (
        <div style={{ marginTop: 8, borderRadius: 8, border: `1px solid ${border}`, background: navy, overflow: "hidden" }}>
          {loading ? (
            <div style={{ padding: 12, fontSize: 11, color: textMuted }}>Loading…</div>
          ) : history?.available ? (
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11 }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${border}` }}>
                  {["Date", "Opponent", "Result", "FP", "Stats"].map((h) => <th key={h} style={{ padding: "6px 8px", textAlign: "left", fontSize: 9, fontWeight: 700, color: textMuted, textTransform: "uppercase" }}>{h}</th>)}
                </tr>
              </thead>
              <tbody>
                {history.games.map((g, i) => (
                  <tr key={i} style={{ borderBottom: `1px solid ${border}40` }}>
                    <td style={{ padding: "6px 8px", color: textSecondary }}>{g.date}</td>
                    <td style={{ padding: "6px 8px", color: textSecondary }}>{g.opponent}</td>
                    <td style={{ padding: "6px 8px", color: textSecondary }}>{g.result}</td>
                    <td style={{ padding: "6px 8px", color: g.fantasy_points == null ? textMuted : gold, fontWeight: 700 }}>{g.fantasy_points == null ? "N/A" : g.fantasy_points.toFixed(1)}</td>
                    <td style={{ padding: "6px 8px", color: textSecondary }}>
                      {Object.entries(g.stats ?? {}).map(([k, v]) => `${k} ${v}`).join(" · ") || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div style={{ padding: 12, fontSize: 11, color: textMuted }}>
              {history?.reason || "Historical player stats unavailable on the current SportsGameOdds subscription — previous-game statistics are not exposed under this tier."}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
