export type PlayerRef = {
  player_id?: string | null;
  name: string;
  found_on_slate?: boolean | null;
  salary?: number | null;
  projected_fp?: number | null;
};

export type ConversationContext = {
  sport?: string | null;
  platform?: string | null;
  slate_id?: number | null;
  slate_name?: string | null;
  slate_start_time?: string | null;
  slate_status?: string | null;
  selected_players?: PlayerRef[];
  locked_players?: PlayerRef[];
  excluded_players?: PlayerRef[];
  requested_metrics?: string[];
  requested_action?: string | null;
  contest_type?: string | null;
  salary_cap?: number | null;
};

export type SuggestedAction = {
  id: string;
  label: string;
  prompt?: string | null;
  href?: string | null;
};

export const EMPTY_AI_CONTEXT: ConversationContext = {
  selected_players: [],
  locked_players: [],
  excluded_players: [],
  requested_metrics: [],
};

export function buildOptimizerHandoffUrl(ctx: ConversationContext): string {
  const params = new URLSearchParams();
  if (ctx.sport) params.set("sport", ctx.sport);
  if (ctx.platform) params.set("platform", ctx.platform);
  if (ctx.slate_id) params.set("slate", String(ctx.slate_id));
  const locks = (ctx.locked_players || []).map((p) => p.name).filter(Boolean);
  if (locks.length) params.set("lock", locks.join(","));
  const qs = params.toString();
  return qs ? `/optimizer?${qs}` : "/optimizer";
}

export function parseOptimizerHandoff(search: string): {
  sport?: string;
  platform?: string;
  slateId?: number;
  lockedNames: string[];
} {
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  const sport = params.get("sport") || undefined;
  const platform = params.get("platform") || undefined;
  const slateRaw = params.get("slate");
  const slateId = slateRaw ? Number(slateRaw) : undefined;
  const lockParam = params.get("lock") || "";
  const lockedNames = lockParam
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  return {
    sport: sport ? sport.toUpperCase() : undefined,
    platform: platform ? platform.toLowerCase() : undefined,
    slateId: Number.isFinite(slateId) ? slateId : undefined,
    lockedNames,
  };
}

export function formatContextStrip(ctx: ConversationContext): string {
  const parts: string[] = [];
  if (ctx.platform === "draftkings") parts.push("DraftKings");
  else if (ctx.platform === "fanduel") parts.push("FanDuel");
  else if (ctx.platform) parts.push(ctx.platform);
  if (ctx.sport) parts.push(ctx.sport);
  if (ctx.slate_name) parts.push(ctx.slate_name);
  else if (ctx.slate_id) parts.push(`slate ${ctx.slate_id}`);
  if (ctx.slate_status) parts.push(ctx.slate_status);
  const lock = (ctx.locked_players || [])[0];
  if (lock?.name) parts.push(`${lock.name} locked`);
  return parts.join(" · ");
}
