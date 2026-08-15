"use client";

import { useState } from "react";
import { formatBookmakerName } from "./bookmakers";

/**
 * Canonical visual asset layer for teams, players, and bookmakers.
 *
 * SGO does not currently expose logo/headshot image URLs under the account
 * tier, so these components degrade gracefully: team → abbreviation chip,
 * player → branded initials avatar, bookmaker → formatted name. When a
 * licensed/provider asset URL becomes available (team.logo_url /
 * player.headshot_url / bookmaker.logo_url), these components render it with
 * a broken-image fallback so a 404 can never render a broken icon.
 *
 * No league/team/player websites are scraped — this is a single lookup point,
 * not per-page duplicated logic.
 */

const gold = "#c9a84c";
const navy = "#060b1a";

/* ── Canonical team logo URL resolver (single source of truth) ── */
export function resolveTeamLogoUrl(team_id?: string | null, abbreviation?: string | null): string | null {
  // No licensed/provider logo URLs are available under the current SGO tier.
  // Return null → caller renders the abbreviation fallback.
  return null;
}

export function resolvePlayerHeadshotUrl(player_id?: string | null, name?: string | null): string | null {
  return null;
}

export function resolveBookmakerLogoUrl(bookmaker_id?: string | null): string | null {
  return null;
}

/* ── Team logo / abbreviation ────────────────────────────────── */
function initialsOf(name: string): string {
  return name
    .split(/\s+/)
    .map((w) => w.charAt(0))
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function teamHue(abbr: string): string {
  // Deterministic pastel hue per team so abbreviations are visually distinct.
  let h = 0;
  for (let i = 0; i < abbr.length; i++) h = (h * 31 + abbr.charCodeAt(i)) % 360;
  return `hsl(${h}, 45%, 28%)`;
}

export function TeamLogo({ team, size = 22 }: { team?: { abbreviation?: string; name?: string; team_id?: string; logo_url?: string | null } | null; size?: number }) {
  const abbr = (team?.abbreviation || team?.name || "?").slice(0, 3).toUpperCase();
  const url = resolveTeamLogoUrl(team?.team_id, abbr) || team?.logo_url;
  const [broken, setBroken] = useState(false);

  if (url && !broken) {
    return (
      <img src={url} alt={abbr} width={size} height={size} onError={() => setBroken(true)}
        style={{ width: size, height: size, objectFit: "contain", borderRadius: 4, display: "inline-block", background: "#0a0f24" }} />
    );
  }
  return (
    <span title={team?.name || abbr}
      style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: size, height: size, borderRadius: 4, fontSize: size * 0.36, fontWeight: 800, color: "#fff", background: teamHue(abbr), letterSpacing: 0.5, flexShrink: 0 }}>
      {abbr}
    </span>
  );
}

/* ── Player headshot / initials avatar ───────────────────────── */
export function PlayerAvatar({ player, size = 26 }: { player?: { name?: string; player_id?: string; headshot_url?: string | null } | null; size?: number }) {
  const name = player?.name || "";
  const url = resolvePlayerHeadshotUrl(player?.player_id, name) || player?.headshot_url;
  const [broken, setBroken] = useState(false);

  if (url && !broken) {
    return (
      <img src={url} alt={name} width={size} height={size} onError={() => setBroken(true)}
        style={{ width: size, height: size, objectFit: "cover", borderRadius: "50%", display: "inline-block", background: "#0a0f24", border: `1px solid ${gold}40` }} />
    );
  }
  return (
    <span title={name}
      style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: size, height: size, borderRadius: "50%", fontSize: size * 0.38, fontWeight: 800, color: gold, background: "linear-gradient(135deg, #0a0f24, #10162f)", border: `1px solid ${gold}55`, flexShrink: 0 }}>
      {initialsOf(name) || "SB"}
    </span>
  );
}

/* ── Bookmaker logo / name ───────────────────────────────────── */
export function BookmakerLogo({ bookmaker, size = 18 }: { bookmaker?: string | null; size?: number }) {
  const name = formatBookmakerName(bookmaker);
  const url = resolveBookmakerLogoUrl(bookmaker) as string | null;
  const [broken, setBroken] = useState(false);

  if (url && !broken) {
    return (
      <img src={url} alt={name} height={size} onError={() => setBroken(true)}
        style={{ height: size, width: "auto", maxWidth: size * 4, objectFit: "contain", display: "inline-block" }} />
    );
  }
  return <span style={{ fontSize: Math.max(10, size * 0.6), fontWeight: 600, color: "#94a3b8", whiteSpace: "nowrap" }}>{name}</span>;
}

/* ── Re-export for convenience ───────────────────────────────── */
export { formatBookmakerName } from "./bookmakers";
