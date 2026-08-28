"use client";

import { useState, useEffect } from "react";
import { ChevronDown, ChevronUp, History } from "lucide-react";

/**
 * Canonical Player Last-5 Game History.
 *
 * Uses GET /api/players/{id}/last-n (finalized SGO results + MLBScorekeeper).
 * Do not call /api/sgo/players/{id}/stats — that dedicated path is unconfirmed.
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
  fantasy_points: number | null;
  stats: Record<string, string | number>;
}

export interface PlayerHistory {
  available: boolean;
  reason?: string;
  games: PlayerHistoryGame[];
}

export interface LastFivePlayer {
  name?: string;
  player_id?: string;
  id?: string;
  sgo_player_id?: string | null;
  team?: string;
  sport?: string;
  slate_id?: number;
}

export async function fetchPlayerHistory(
  playerId: string,
  platform: string,
  extras?: { name?: string; team?: string; sport?: string; slateId?: number },
): Promise<PlayerHistory> {
  const base = (typeof process !== "undefined" ? process.env.NEXT_PUBLIC_API_URL : undefined) || "https://sportbook-me-production.up.railway.app";
  const token = (typeof window !== "undefined" && localStorage.getItem("sbme_dfs_token")) || "";
  const params = new URLSearchParams({
    platform: platform || "draftkings",
    n: "5",
    sport: extras?.sport || "MLB",
  });
  if (extras?.name) params.set("name", extras.name);
  if (extras?.team) params.set("team", extras.team);
  if (extras?.slateId) params.set("slate_id", String(extras.slateId));
  try {
    const res = await fetch(`${base}/api/players/${encodeURIComponent(playerId)}/last-n?${params.toString()}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    const json = await res.json().catch(() => ({}));
    const payload = json?.data ?? json ?? {};
    if (!res.ok) {
      return {
        available: false,
        reason: payload?.reason || payload?.detail || `HTTP ${res.status}`,
        games: [],
      };
    }
    const games = payload.games ?? [];
    return {
      available: Boolean(payload.available) && Array.isArray(games) && games.length > 0,
      reason: payload.reason,
      games: Array.isArray(games) ? games.slice(0, 5) : [],
    };
  } catch {
    return { available: false, reason: "Historical stats fetch failed.", games: [] };
  }
}

export function LastFive({
  player,
  platform = "draftkings",
}: {
  player: LastFivePlayer | null | undefined;
  platform?: string;
}) {
  const [open, setOpen] = useState(false);
  const [history, setHistory] = useState<PlayerHistory | null>(null);
  const [loading, setLoading] = useState(false);
  const pid = player?.sgo_player_id || player?.player_id || player?.id || "";

  useEffect(() => {
    if (!open || !pid) return;
    let cancelled = false;
    setLoading(true);
    fetchPlayerHistory(pid, platform, {
      name: player?.name,
      team: player?.team,
      sport: player?.sport,
      slateId: player?.slate_id,
    }).then((h) => {
      if (!cancelled) {
        setHistory(h);
        setLoading(false);
      }
    });
    return () => { cancelled = true; };
  }, [open, pid, platform, player?.name, player?.team, player?.sport, player?.slate_id]);

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
              {history?.reason || "No completed-game history is available for this player."}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
