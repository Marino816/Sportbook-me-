import {
  averageRemainingPerPlayer,
  getRoster,
  slotEligible,
  slotLabel,
} from "./dfs-roster.mjs";

export { averageRemainingPerPlayer, getRoster, slotEligible, slotLabel };

export function playerKey(player) {
  return String(player?.player_id || player?.sbme_player_id || player?.id || player?.name || "").trim();
}

export function isOpenSlate(slate) {
  const fresh = String(slate?.freshness || "").toUpperCase();
  if (fresh === "STALE" || fresh === "LOCKED" || fresh === "ARCHIVED") return false;
  if (slate?.is_current === true) return true;
  return fresh === "CURRENT" || fresh === "FRESH";
}

export function filterOpenSlates(slates) {
  return (Array.isArray(slates) ? slates : []).filter(isOpenSlate);
}

export function emptySlots(roster) {
  return (roster?.slots || []).map(() => null);
}

export function lineupFillMode(slots) {
  const list = Array.isArray(slots) ? slots : [];
  const filled = list.filter(Boolean).length;
  if (filled === 0) return "empty";
  if (list.length > 0 && filled >= list.length) return "full";
  return "partial";
}

export function usedSalary(slots) {
  return (Array.isArray(slots) ? slots : []).reduce((sum, player) => sum + Number(player?.salary || 0), 0);
}

export function remainingSalary(cap, slots) {
  return Number(cap || 0) - usedSalary(slots);
}

export function displayProjection(player) {
  for (const value of [player?.projected_fp, player?.bc_beta_proj, player?.fppg]) {
    if (value === undefined || value === null || value === "") continue;
    const n = Number(value);
    if (Number.isFinite(n)) return n;
  }
  return null;
}

export function validatePlayerSelection({ player, slotIndex, slots, roster }) {
  if (!roster) return { ok: false, reason: "No roster rules for this sport and platform." };
  const slot = roster.slots[slotIndex];
  if (!slot) return { ok: false, reason: "Invalid roster slot." };
  const pos = player?.eligible_positions || player?.position;
  if (!slotEligible(pos, slot, roster)) {
    return { ok: false, reason: `${player?.name || "Player"} is not eligible for ${slotLabel(slot, roster)}.` };
  }
  const key = playerKey(player);
  const duplicate = (slots || []).some((item, idx) => item && idx !== slotIndex && playerKey(item) === key);
  if (duplicate) return { ok: false, reason: "That player is already in the lineup." };
  const cap = roster.salaryCap ?? 0;
  const outgoing = Number(slots?.[slotIndex]?.salary || 0);
  const next = usedSalary(slots) - outgoing + Number(player?.salary || 0);
  if (cap && next > cap) {
    return {
      ok: false,
      reason: "This player exceeds the remaining salary cap. Choose a lower-salary replacement.",
    };
  }
  return { ok: true };
}

export function validateFullManualLineup(slots, roster) {
  if (!roster) return { ok: false, reason: "No roster rules for this sport and platform." };
  const list = Array.isArray(slots) ? slots : [];
  if (list.length !== roster.slots.length || list.some((player) => !player)) {
    return { ok: false, reason: "Lineup is not complete." };
  }
  const seen = new Set();
  let salary = 0;
  let proj = 0;
  const players = [];
  for (let i = 0; i < roster.slots.length; i += 1) {
    const player = list[i];
    const slot = roster.slots[i];
    const key = playerKey(player);
    if (!key || seen.has(key)) return { ok: false, reason: "Duplicate player in lineup." };
    seen.add(key);
    if (!slotEligible(player.eligible_positions || player.position, slot, roster)) {
      return { ok: false, reason: `${player.name} is not eligible for ${slotLabel(slot, roster)}.` };
    }
    salary += Number(player.salary || 0);
    proj += Number(displayProjection(player) || 0);
    players.push({
      ...player,
      roster_slot: slotLabel(slot, roster),
      projected_fp: displayProjection(player),
    });
  }
  if (roster.salaryCap != null && salary > roster.salaryCap) {
    return { ok: false, reason: "Lineup exceeds the salary cap." };
  }
  if (roster.minSalary && salary < roster.minSalary) {
    return { ok: false, reason: `Lineup is below the minimum salary (${roster.minSalary}).` };
  }
  return { ok: true, lineup: { total_salary: salary, projected_score: Number(proj.toFixed(1)), players } };
}

export function solverLockKeys(keys, pool) {
  const out = new Set();
  for (const raw of keys || []) {
    const trimmed = String(raw || "").trim();
    if (!trimmed) continue;
    out.add(trimmed);
    const hit = (pool || []).find((player) => playerKey(player) === trimmed || String(player?.name || "") === trimmed);
    if (hit?.player_id) out.add(String(hit.player_id));
    if (hit?.name) out.add(String(hit.name));
  }
  return Array.from(out);
}

export function buildOptimizeSettings({
  platform,
  strategy,
  numLineups,
  sport,
  stackSize,
  exposure,
  lockKeys,
  pool,
  regenerateFromIds,
}) {
  const settings = {
    platform,
    strategy,
    num_lineups: numLineups,
    sport,
  };
  if (String(sport || "").toLowerCase() === "mlb" && stackSize != null) settings.stack_size = stackSize;
  if (exposure != null) settings.max_exposure_pct = exposure;
  settings.locked_player_ids = solverLockKeys(lockKeys || [], pool || []);
  if (Array.isArray(regenerateFromIds) && regenerateFromIds.length) {
    settings.regenerate_from_ids = regenerateFromIds;
  }
  return settings;
}

export function gameLabel(player) {
  const info = String(player?.game_info || "").trim();
  if (info) {
    const first = info.split(/\s+/)[0];
    if (first.includes("@")) return first.toUpperCase();
  }
  const team = String(player?.team || "").toUpperCase();
  const opp = String(player?.opponent || "").toUpperCase();
  if (team && opp && opp !== "OPP") return `${team}@${opp}`;
  return "";
}

export function extractGames(players) {
  const seen = [];
  for (const player of players || []) {
    const label = gameLabel(player);
    if (label && !seen.includes(label)) seen.push(label);
  }
  return seen;
}

export function playerMatchesGame(player, game) {
  if (!game || game === "ALL") return true;
  return gameLabel(player) === game;
}

const DRAFT_TITLES = {
  QB: "Draft Quarterback",
  RB: "Draft Running Back",
  WR: "Draft Wide Receiver",
  TE: "Draft Tight End",
  DST: "Draft DST",
  DEF: "Draft DST",
  FLEX: "Draft Flex",
  SFLX: "Draft Super Flex",
  P: "Draft Pitcher",
  C: "Draft Catcher",
  "1B": "Draft First Base",
  "2B": "Draft Second Base",
  "3B": "Draft Third Base",
  SS: "Draft Shortstop",
  OF: "Draft Outfield",
  C1B: "Draft Catcher / First Base",
  UTIL: "Draft Utility",
};

export function draftTitle(slot, roster) {
  const key = String(slot || "").toUpperCase();
  if (DRAFT_TITLES[key]) return DRAFT_TITLES[key];
  const label = slotLabel(slot, roster);
  return label ? `Draft ${label}` : "Draft Player";
}

function firstString(...values) {
  for (const value of values) {
    if (value == null || value === "") continue;
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return "";
}

function firstFinite(...values) {
  for (const value of values) {
    if (value === undefined || value === null || value === "") continue;
    const n = Number(value);
    if (Number.isFinite(n)) return n;
  }
  return null;
}

export function formatAmericanOdds(value) {
  const n = firstFinite(value);
  if (n == null) return "";
  const v = Math.round(n);
  return v > 0 ? `+${v}` : `${v}`;
}

export function parseGameInfo(gameInfo, fallbackStart) {
  const info = String(gameInfo || "").trim();
  const out = { matchup: "", date: "", time: "" };
  if (info) {
    const parts = info.split(/\s+/).filter(Boolean);
    const matchup = parts.find((part) => part.includes("@"));
    if (matchup) out.matchup = matchup.toUpperCase();
    const datePart = parts.find((part) => /^\d{1,2}\/\d{1,2}/.test(part));
    if (datePart) out.date = datePart;
    const timeIdx = parts.findIndex((part) => /^\d{1,2}:\d{2}/.test(part));
    if (timeIdx >= 0) {
      const rest = parts.slice(timeIdx);
      const et = rest.findIndex((part) => /^ET$/i.test(part));
      out.time = (et >= 0 ? rest.slice(0, et + 1) : rest.slice(0, 2)).join(" ");
    }
  }
  if (fallbackStart) {
    const d = new Date(fallbackStart);
    if (!Number.isNaN(d.getTime())) {
      if (!out.date) {
        out.date = d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
      }
      if (!out.time) {
        out.time = d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
      }
    }
  }
  return out;
}

export function matchOddsToGame(label, oddsGames) {
  const key = String(label || "").toUpperCase();
  if (!key.includes("@")) return null;
  const [left, right] = key.split("@");
  for (const game of oddsGames || []) {
    const home = String(game?.home_abbr || game?.home_team || "").toUpperCase();
    const away = String(game?.away_abbr || game?.away_team || "").toUpperCase();
    if (home && away && ((away === left && home === right) || (home === left && away === right))) {
      return game;
    }
  }
  return null;
}

export function extractGameCards(players, { slateStart, oddsGames } = {}) {
  const cards = [];
  const seen = new Set();
  for (const player of players || []) {
    const id = gameLabel(player);
    if (!id || seen.has(id)) continue;
    seen.add(id);
    const parsed = parseGameInfo(player.game_info, player.game_start || player.start_time || slateStart);
    const odds = matchOddsToGame(id, oddsGames);
    const weather = firstString(
      player.weather,
      player.game_weather,
      odds?.weather,
      typeof odds?.sbme_environment?.weather === "string" ? odds.sbme_environment.weather : "",
    );
    const mlHome = formatAmericanOdds(odds?.moneyline_home);
    const mlAway = formatAmericanOdds(odds?.moneyline_away);
    const spread = firstFinite(odds?.spread_line);
    const total = firstFinite(odds?.total_line);
    cards.push({
      id,
      matchup: parsed.matchup || id,
      date: parsed.date,
      time: parsed.time,
      weather,
      moneyline: mlHome && mlAway ? `${mlAway} / ${mlHome}` : mlHome || mlAway,
      spread: spread == null ? "" : `${spread > 0 ? "+" : ""}${spread}`,
      total: total == null ? "" : `O/U ${total}`,
    });
  }
  return cards;
}

export function salaryFooterStats({ slots, cap, roster }) {
  const total = roster?.slots?.length || (Array.isArray(slots) ? slots.length : 0);
  const filled = (Array.isArray(slots) ? slots : []).filter(Boolean).length;
  const remaining = remainingSalary(cap, slots);
  const openSlots = Math.max(0, total - filled);
  return {
    filled,
    total,
    remaining,
    underCap: remaining >= 0,
    avgRemaining: averageRemainingPerPlayer(remaining, openSlots),
  };
}

function truthyFlag(value) {
  if (value === true || value === 1) return true;
  const text = String(value || "").trim().toLowerCase();
  return text === "true" || text === "yes" || text === "y" || text === "confirmed";
}

export function confirmedBattingOrder(player) {
  const order = firstFinite(
    player?.batting_order,
    player?.lineup_order,
    player?.battingOrder,
    player?.order_in_lineup,
  );
  if (order == null || order <= 0) return null;
  const confirmed = truthyFlag(
    player?.lineup_confirmed
      ?? player?.confirmed_lineup
      ?? player?.batting_order_confirmed
      ?? player?.starter_confirmed,
  );
  if (!confirmed) return null;
  return Math.round(order);
}

export function batsDisplay(player) {
  const bats = firstString(player?.bats, player?.batting_hand, player?.bat_hand);
  const upper = bats.toUpperCase();
  if (upper === "L" || upper === "R" || upper === "S") return upper;
  if (upper === "LEFT") return "L";
  if (upper === "RIGHT") return "R";
  if (upper === "SWITCH") return "S";
  return "";
}

export function probablePitcher(player) {
  return firstString(
    player?.probable_pitcher,
    player?.opposing_pitcher,
    player?.opp_pitcher,
    player?.opp_probable_pitcher,
  );
}

export function opponentRank(player) {
  const rank = firstFinite(player?.opp_rank, player?.opponent_rank, player?.dvp_rank);
  return rank == null ? null : Math.round(rank);
}

export function isConfirmedStarter(player) {
  if (truthyFlag(player?.confirmed_starter) || truthyFlag(player?.is_confirmed_starter)) return true;
  const status = String(player?.starter_status || player?.lineup_status || "").toLowerCase();
  if (status === "confirmed" || status === "starting") return true;
  return false;
}

export function hasStarterData(players) {
  return (players || []).some((player) => isConfirmedStarter(player));
}

export function eligiblePositionsLabel(player) {
  if (Array.isArray(player?.eligible_positions) && player.eligible_positions.length) {
    return player.eligible_positions.filter(Boolean).join("/");
  }
  return String(player?.position || "").trim();
}

export function playerMatchupLine(player) {
  return gameLabel(player) || firstString(player?.team && player?.opponent ? `${player.team}@${player.opponent}` : "");
}

export function playerGameTime(player, slateStart) {
  return parseGameInfo(player?.game_info, player?.game_start || player?.start_time || slateStart).time;
}

export function sortPlayersBySalary(players, direction) {
  return [...(players || [])].sort((a, b) => {
    const delta = Number(a?.salary || 0) - Number(b?.salary || 0);
    return direction === "low" ? delta : -delta;
  });
}

export function applyLineupToSlots(lineup, roster) {
  const slots = emptySlots(roster);
  const players = Array.isArray(lineup?.players) ? lineup.players : [];
  const used = new Set();
  for (let i = 0; i < (roster?.slots || []).length; i += 1) {
    const slot = roster.slots[i];
    const label = slotLabel(slot, roster).toUpperCase();
    let found = -1;
    for (let j = 0; j < players.length; j += 1) {
      if (used.has(j)) continue;
      const raw = String(players[j]?.roster_slot || players[j]?.assigned_slot || players[j]?.roster_position || "").toUpperCase();
      if (raw === label || raw === slot.toUpperCase()) {
        found = j;
        break;
      }
    }
    if (found < 0) {
      for (let j = 0; j < players.length; j += 1) {
        if (used.has(j)) continue;
        if (slotEligible(players[j]?.eligible_positions || players[j]?.position || players[j]?.roster_slot, slot, roster)) {
          found = j;
          break;
        }
      }
    }
    if (found >= 0) {
      used.add(found);
      slots[i] = players[found];
    }
  }
  return slots;
}

export function shouldClearResultState(prev, next) {
  return String(prev?.strategy || "") !== String(next?.strategy || "")
    || Number(prev?.count) !== Number(next?.count);
}

export function lockKeysFromSlots(slots) {
  return (slots || []).filter(Boolean).map(playerKey).filter(Boolean);
}

export function regenerateIdsFromLineup(lineup) {
  return (lineup?.players || []).map(playerKey).filter(Boolean);
}

export const OPEN_OPTIMIZER_COPY = "Open Optimizer to review roster, strategy, players and build.";
export const BUILD_BUTTON_LABEL = "BUILD OPTIMAL LINEUP";
export const OPEN_OPTIMIZER_LABEL = "OPEN OPTIMIZER";
