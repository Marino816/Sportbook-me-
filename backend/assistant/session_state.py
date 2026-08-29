"""
Structured SB ME Intelligence conversation state.

The LLM must not be the only memory. Sport, platform, slate, players, and
the requested action live in an explicit object that is merged on every
turn and injected as authoritative session context.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dfs.name_normalize import fold_player_name, names_equal


from dfs.roster import get_roster

SALARY_CAPS = {"draftkings": 50000, "fanduel": 35000}

SPORT_ALIASES = {
    "mlb": "MLB",
    "nba": "NBA",
    "nfl": "NFL",
    "nhl": "NHL",
    "ncaaf": "NCAAF",
    "ncaab": "NCAAB",
    "wnba": "WNBA",
    "mls": "MLS",
    "epl": "EPL",
}

PLATFORM_CANON = {
    "draftkings": "draftkings",
    "draft kings": "draftkings",
    "dk": "draftkings",
    "fanduel": "fanduel",
    "fan duel": "fanduel",
    "fd": "fanduel",
}

STOP_NAME_TOKENS = {
    "draftkings", "draft", "kings", "fanduel", "fan", "duel", "mlb", "nba",
    "nfl", "nhl", "slate", "lineup", "lineups", "metrics", "this", "that",
    "the", "a", "an", "on", "for", "with", "and", "unlocked", "locked",
    "main", "games", "players", "platform", "sport",
}

OPTIMIZER_RE = re.compile(
    r"\b("
    r"build(?:\s+me)?(?:\s+a)?\s+lineup|"
    r"make(?:\s+me)?(?:\s+a)?\s+lineup|"
    r"build\s+around|"
    r"optimize(?:\s+this)?(?:\s+slate)?|"
    r"give\s+me\s+the\s+best\s+lineup|"
    r"build\s+it|"
    r"lock\s+.+\s+and\s+build"
    r")\b",
    re.I,
)
METRICS_RE = re.compile(
    r"\b(sb\s*me\s+metrics?|sbme\s+metrics?|optimal%|sb\s*own%?|leverage|"
    r"ceiling|floor)\b",
    re.I,
)
PLATFORM_RE = re.compile(
    r"\b(draft\s*kings|fan\s*duel|fanduel|dk|fd)\b",
    re.I,
)
SPORT_RE = re.compile(
    r"\b(mlb|nba|nfl|nhl|ncaaf|ncaab|wnba|mls|epl)\b",
    re.I,
)
TIME_RE = re.compile(r"\b(\d{1,2}):(\d{2})\s*(a\.?m\.?|p\.?m\.?)?\b", re.I)
PLAYER_COUNT_RE = re.compile(r"\b(\d{1,3}(?:,\d{3})+|\d{3,5})\s*players?\b", re.I)
AROUND_RE = re.compile(
    r"\b(?:around|lock(?:ing)?)\s+([A-Za-z][A-Za-z.'\-]+(?:\s+[A-Za-z][A-Za-z.'\-]+){1,3})",
    re.I,
)
EXCLUDE_RE = re.compile(
    r"\b(?:exclude|sit|bench)\s+([A-Za-z][A-Za-z.'\-]+(?:\s+[A-Za-z][A-Za-z.'\-]+){1,3})",
    re.I,
)
CONTEST_RE = re.compile(r"\b(cash|gpp|tournament|single[\s-]?entry|nuclear)\b", re.I)
# "slate id 29", "id 29", "slate #29" — do not capture times like "slate 6:40".
SLATE_ID_RE = re.compile(
    r"(?:slate\s*(?:id|#)\s*|id\s+#?\s*)(\d{1,6})\b|(?:slate\s+)(\d{2,6})\b(?!\s*:)",
    re.I,
)


class PlayerRef(BaseModel):
    player_id: Optional[str] = None
    name: str
    found_on_slate: Optional[bool] = None
    salary: Optional[int] = None
    projected_fp: Optional[float] = None


class SuggestedAction(BaseModel):
    id: str
    label: str
    prompt: Optional[str] = None
    href: Optional[str] = None


class ConversationContext(BaseModel):
    sport: Optional[str] = None
    platform: Optional[str] = None
    slate_id: Optional[int] = None
    slate_name: Optional[str] = None
    slate_start_time: Optional[str] = None
    slate_status: Optional[str] = None
    selected_players: list[PlayerRef] = Field(default_factory=list)
    locked_players: list[PlayerRef] = Field(default_factory=list)
    excluded_players: list[PlayerRef] = Field(default_factory=list)
    requested_metrics: list[str] = Field(default_factory=list)
    requested_action: Optional[str] = None
    contest_type: Optional[str] = None
    salary_cap: Optional[int] = None

    def missing_fields(self, needed: Optional[list[str]] = None) -> list[str]:
        keys = needed or ["sport", "platform", "slate_id"]
        missing = []
        for key in keys:
            if not getattr(self, key, None):
                missing.append(key)
        return missing


def _compact(name: str) -> str:
    folded = fold_player_name(name)
    return re.sub(r"[^a-z0-9]", "", folded)


def _looks_like_person_name(raw: str) -> bool:
    tokens = [t for t in re.split(r"\s+", (raw or "").strip()) if t]
    if len(tokens) < 2 or len(tokens) > 4:
        return False
    if any(t.lower().strip(".,") in STOP_NAME_TOKENS for t in tokens):
        return False
    return all(re.match(r"^[A-Za-z][A-Za-z.'\-]*$", t) for t in tokens)


def _canon_platform(text: str) -> Optional[str]:
    key = re.sub(r"\s+", " ", (text or "").strip().lower())
    return PLATFORM_CANON.get(key)


def _extract_platform(message: str) -> Optional[str]:
    m = PLATFORM_RE.search(message or "")
    if not m:
        return None
    return _canon_platform(m.group(1))


def _extract_sport(message: str) -> Optional[str]:
    m = SPORT_RE.search(message or "")
    if not m:
        return None
    return SPORT_ALIASES.get(m.group(1).lower())


def classify_action(message: str) -> Optional[str]:
    text = message or ""
    opt = bool(OPTIMIZER_RE.search(text))
    met = bool(METRICS_RE.search(text))
    if opt and not met:
        return "optimizer"
    if met and not opt:
        return "metrics"
    if opt and met:
        # Last matching intent in the message wins.
        last_opt = list(OPTIMIZER_RE.finditer(text))[-1].start()
        last_met = list(METRICS_RE.finditer(text))[-1].start()
        return "metrics" if last_met > last_opt else "optimizer"
    return None


def is_optimizer_commit(message: str) -> bool:
    return bool(OPTIMIZER_RE.search(message or ""))


def extract_player_names(message: str) -> list[str]:
    names: list[str] = []
    for rx in (AROUND_RE, EXCLUDE_RE):
        for m in rx.finditer(message or ""):
            candidate = re.sub(r"[.,;:]+$", "", m.group(1).strip())
            candidate = re.split(r"\s+(?:on|for|with|in)\s+", candidate, maxsplit=1, flags=re.I)[0]
            if _looks_like_person_name(candidate):
                names.append(candidate)
    # Dedup by compact form, preserve order.
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        key = _compact(n)
        if key and key not in seen:
            seen.add(key)
            out.append(n)
    return out


def extract_slate_id(message: str) -> Optional[int]:
    """Parse an explicit slate id from the customer message. Never invent one."""
    m = SLATE_ID_RE.search(message or "")
    if not m:
        return None
    raw = m.group(1) or m.group(2)
    try:
        sid = int(raw)
    except (TypeError, ValueError):
        return None
    return sid if sid > 0 else None


def extract_excluded_names(message: str) -> list[str]:
    names: list[str] = []
    for m in EXCLUDE_RE.finditer(message or ""):
        candidate = re.sub(r"[.,;:]+$", "", m.group(1).strip())
        if _looks_like_person_name(candidate):
            names.append(candidate)
    return names


def _et_clock(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    try:
        from zoneinfo import ZoneInfo
        local = dt.astimezone(ZoneInfo("America/New_York"))
    except Exception:
        local = dt
    hour = local.hour % 12 or 12
    return f"{hour}:{local.minute:02d}"


def _user_times(message: str) -> list[tuple[int, int]]:
    found = []
    for m in TIME_RE.finditer(message or ""):
        hour = int(m.group(1))
        minute = int(m.group(2))
        ampm = (m.group(3) or "").lower().replace(".", "")
        if ampm.startswith("p") and hour < 12:
            hour += 12
        if ampm.startswith("a") and hour == 12:
            hour = 0
        found.append((hour, minute))
    return found


def _score_slate(message: str, slate: Any) -> int:
    text = unicodedata.normalize("NFKC", message or "").lower()
    text_compact = re.sub(r"[\s–—−-]+", " ", text)
    name = (getattr(slate, "slate_name", None) or "").lower()
    score = 0
    if name and name in text_compact:
        score += 12
    name_tokens = [t for t in re.split(r"\W+", name) if t and t not in {"et", "pm", "am"}]
    for tok in name_tokens:
        if tok in text_compact:
            score += 2
    if "main" in text_compact and "main" in name:
        score += 5
    clock = _et_clock(getattr(slate, "start_time", None))
    if clock:
        clock_l = clock.lower()
        if clock_l in text_compact.replace(" ", ""):
            score += 10
        for hour, minute in _user_times(message):
            h12 = hour % 12 or 12
            if h12 == int(clock.split(":")[0]) and minute == int(clock.split(":")[1]):
                score += 10
                break
    want_count = PLAYER_COUNT_RE.search(message or "")
    if want_count:
        raw = int(want_count.group(1).replace(",", ""))
        if int(getattr(slate, "player_count", 0) or 0) == raw:
            score += 4
    return score


async def match_slate(
    db: AsyncSession,
    message: str,
    sport: Optional[str] = None,
    platform: Optional[str] = None,
) -> Optional[Any]:
    from dfs.db import DFSSlate
    from dfs.freshness import is_ai_matchable_slate

    explicit_id = extract_slate_id(message)
    if explicit_id:
        row = (
            await db.execute(select(DFSSlate).where(DFSSlate.id == explicit_id))
        ).scalars().first()
        if row and is_ai_matchable_slate(row.status, row.start_time, row.sport):
            if sport and str(row.sport).upper() != str(sport).upper():
                return None
            if platform and str(row.platform).lower() != str(platform).lower():
                return None
            return row
        return None

    q = select(DFSSlate).where(DFSSlate.status.in_(["PUBLISHED", "DRAFT"]))
    if platform:
        q = q.where(DFSSlate.platform == platform.lower())
    if sport:
        q = q.where(DFSSlate.sport == sport.upper())
    q = q.order_by(DFSSlate.start_time.asc())
    rows = (await db.execute(q)).scalars().all()
    from dfs.freshness import is_ai_matchable_slate
    rows = [s for s in rows if is_ai_matchable_slate(s.status, s.start_time, s.sport)]
    if not rows:
        return None

    scored = [(s, _score_slate(message, s)) for s in rows]
    scored.sort(key=lambda x: x[1], reverse=True)
    best, best_score = scored[0]
    if best_score >= 6:
        # Require uniqueness if two slates are close.
        if len(scored) > 1 and scored[1][1] == best_score:
            return None
        return best
    if len(rows) == 1 and best_score >= 3:
        return best
    return None


def _upsert_player(bucket: list[PlayerRef], name: str) -> PlayerRef:
    compact = _compact(name)
    for existing in bucket:
        if _compact(existing.name) == compact:
            return existing
    ref = PlayerRef(name=name)
    bucket.append(ref)
    return ref


def _apply_salary_cap(ctx: ConversationContext) -> None:
    roster = get_roster(ctx.sport, ctx.platform) if ctx.sport and ctx.platform else None
    if roster and roster.salary_cap is not None:
        ctx.salary_cap = roster.salary_cap
    elif ctx.platform:
        # MLB-era fallback only when sport is unknown.
        ctx.salary_cap = SALARY_CAPS.get(ctx.platform)


def _slate_status_label(start_time: Optional[datetime]) -> str:
    from dfs.optimal_lock import is_slate_locked
    return "LOCKED" if is_slate_locked(start_time) else "UNLOCKED"


def apply_slate(ctx: ConversationContext, slate: Any) -> None:
    ctx.slate_id = int(slate.id)
    ctx.slate_name = slate.slate_name
    start = slate.start_time
    ctx.slate_start_time = start.isoformat() if start else None
    ctx.slate_status = _slate_status_label(start)
    if not ctx.sport and getattr(slate, "sport", None):
        ctx.sport = str(slate.sport).upper()
    if not ctx.platform and getattr(slate, "platform", None):
        ctx.platform = str(slate.platform).lower()
    _apply_salary_cap(ctx)


async def _resolve_players_on_slate(
    db: AsyncSession,
    ctx: ConversationContext,
) -> None:
    if not ctx.slate_id:
        return
    from dfs.db import DFSPlayer

    rows = (
        await db.execute(select(DFSPlayer).where(DFSPlayer.slate_id == ctx.slate_id))
    ).scalars().all()
    by_compact = {_compact(p.player_name or ""): p for p in rows if p.player_name}

    def _bind(ref: PlayerRef) -> None:
        hit = by_compact.get(_compact(ref.name))
        if hit is None:
            for p in rows:
                if names_equal(p.player_name, ref.name):
                    hit = p
                    break
        if hit is None:
            ref.found_on_slate = False
            ref.player_id = None
            return
        ref.found_on_slate = True
        ref.player_id = hit.sbme_player_id or hit.provider_player_id
        ref.name = hit.player_name or ref.name
        ref.salary = hit.salary

    for ref in ctx.locked_players + ctx.selected_players + ctx.excluded_players:
        _bind(ref)


async def _remap_slate_for_platform(
    db: AsyncSession,
    ctx: ConversationContext,
    new_platform: str,
) -> None:
    """Keep sport/players; move to an equivalent slate on the new platform if possible."""
    if not ctx.slate_id:
        return
    from dfs.db import DFSSlate

    current = (
        await db.execute(select(DFSSlate).where(DFSSlate.id == ctx.slate_id))
    ).scalars().first()
    ctx.slate_id = None
    ctx.slate_name = None
    ctx.slate_start_time = None
    ctx.slate_status = None
    if current is None:
        return
    q = select(DFSSlate).where(
        DFSSlate.status == "PUBLISHED",
        DFSSlate.platform == new_platform,
        DFSSlate.sport == (ctx.sport or current.sport),
    )
    candidates = (await db.execute(q)).scalars().all()
    hint = current.slate_name or ""
    clock = _et_clock(current.start_time) or ""
    best = None
    best_score = -1
    for s in candidates:
        score = _score_slate(f"{hint} {clock}", s)
        if score > best_score:
            best, best_score = s, score
    if best is not None and best_score >= 5:
        apply_slate(ctx, best)


async def merge_conversation_context(
    previous: Optional[ConversationContext],
    message: str,
    db: AsyncSession,
    *,
    sport: Optional[str] = None,
    platform: Optional[str] = None,
    slate_id: Optional[int] = None,
) -> ConversationContext:
    """Merge this turn's utterance into explicit session state."""
    ctx = (previous or ConversationContext()).model_copy(deep=True)

    if sport and not ctx.sport:
        ctx.sport = sport.upper()
    if platform and not ctx.platform:
        ctx.platform = _canon_platform(platform) or platform.lower()
    if slate_id:
        from dfs.db import DFSSlate
        row = (
            await db.execute(select(DFSSlate).where(DFSSlate.id == int(slate_id)))
        ).scalars().first()
        if row:
            apply_slate(ctx, row)

    extracted_platform = _extract_platform(message)
    if extracted_platform:
        if ctx.platform and ctx.platform != extracted_platform:
            await _remap_slate_for_platform(db, ctx, extracted_platform)
        ctx.platform = extracted_platform
        _apply_salary_cap(ctx)

    extracted_sport = _extract_sport(message)
    if extracted_sport:
        if ctx.sport and ctx.sport != extracted_sport:
            ctx.slate_id = None
            ctx.slate_name = None
            ctx.slate_start_time = None
            ctx.slate_status = None
        ctx.sport = extracted_sport

    action = classify_action(message)
    if action:
        ctx.requested_action = action
        if action == "metrics" and "sb_metrics" not in ctx.requested_metrics:
            ctx.requested_metrics = [
                "projection", "salary", "value", "sb_own", "leverage",
                "ceiling", "floor", "optimal_pct",
            ]

    contest = CONTEST_RE.search(message or "")
    if contest:
        ctx.contest_type = contest.group(1).lower().replace(" ", "-")

    for name in extract_player_names(message):
        ref = _upsert_player(ctx.selected_players, name)
        if AROUND_RE.search(message or "") or re.search(r"\block(?:ing)?\b", message or "", re.I):
            locked = _upsert_player(ctx.locked_players, name)
            locked.name = ref.name

    for name in extract_excluded_names(message):
        _upsert_player(ctx.excluded_players, name)

    matched = await match_slate(db, message, sport=ctx.sport, platform=ctx.platform)
    if matched is not None:
        apply_slate(ctx, matched)

    if ctx.slate_id:
        from dfs.db import DFSSlate
        row = (
            await db.execute(select(DFSSlate).where(DFSSlate.id == ctx.slate_id))
        ).scalars().first()
        if row:
            ctx.slate_status = _slate_status_label(row.start_time)
            ctx.slate_name = row.slate_name or ctx.slate_name
            if row.start_time:
                ctx.slate_start_time = row.start_time.isoformat()

    await _resolve_players_on_slate(db, ctx)
    _apply_salary_cap(ctx)
    return ctx


async def absorb_slate_from_tool_results(
    ctx: ConversationContext,
    tool_results: list[tuple[str, dict]],
    db: AsyncSession,
) -> ConversationContext:
    """If session still has no slate_id, take a unique slate from tool output.

    Never guess among multiple slates. Never invent names or times.
    """
    if ctx.slate_id:
        return ctx
    from dfs.db import DFSSlate

    candidates: list[int] = []
    for name, payload in tool_results or []:
        if not isinstance(payload, dict):
            continue
        if name == "get_current_slates":
            slates = payload.get("slates") or []
            ids = [int(s["slate_id"]) for s in slates if isinstance(s, dict) and s.get("slate_id")]
            if len(ids) == 1:
                candidates.append(ids[0])
        sid = payload.get("slate_id")
        if isinstance(sid, int) and sid > 0:
            candidates.append(sid)
    uniq = list(dict.fromkeys(candidates))
    if len(uniq) != 1:
        return ctx
    row = (
        await db.execute(select(DFSSlate).where(DFSSlate.id == uniq[0]))
    ).scalars().first()
    if row:
        apply_slate(ctx, row)
        await _resolve_players_on_slate(db, ctx)
        _apply_salary_cap(ctx)
    return ctx


def render_session_note(ctx: ConversationContext) -> str:
    missing = ctx.missing_fields()
    known_lines = []
    if ctx.sport:
        known_lines.append(f"sport = {ctx.sport}")
    if ctx.platform:
        known_lines.append(f"platform = {ctx.platform}")
    if ctx.slate_id:
        known_lines.append(f"slate_id = {ctx.slate_id}")
    if ctx.slate_name:
        known_lines.append(f"slate_name = {ctx.slate_name}")
    if ctx.slate_start_time:
        known_lines.append(f"slate_start_time = {ctx.slate_start_time}")
    if ctx.slate_status:
        known_lines.append(f"slate_status = {ctx.slate_status}")
    if ctx.salary_cap:
        known_lines.append(f"salary_cap = {ctx.salary_cap}")
    if ctx.contest_type:
        known_lines.append(f"contest_type = {ctx.contest_type}")
    if ctx.requested_action:
        known_lines.append(f"requested_action = {ctx.requested_action}")
    if ctx.requested_metrics:
        known_lines.append("requested_metrics = " + ", ".join(ctx.requested_metrics))
    if ctx.locked_players:
        bits = []
        for p in ctx.locked_players:
            extra = f" id={p.player_id}" if p.player_id else ""
            found = "found" if p.found_on_slate else ("NOT on slate" if p.found_on_slate is False else "unresolved")
            bits.append(f"{p.name}{extra} ({found})")
        known_lines.append("locked_players = " + "; ".join(bits))
    if ctx.excluded_players:
        known_lines.append("excluded_players = " + ", ".join(p.name for p in ctx.excluded_players))

    rules = [
        "KNOWN SESSION STATE is authoritative. Do not re-ask for any field listed above.",
        "Ask ONLY for missing fields listed below. If none are missing, ask nothing about sport/platform/slate.",
        "Never say you would be happy to help with a sport that is already known.",
        "If a locked player is marked NOT on slate, say exactly: \"<Name> is not in this selected slate.\" Do not invent eligibility.",
        "If slate_status is LOCKED, you may analyze the slate but must explain that new contest lineup submission/optimization may no longer be useful for entry. Do not re-ask whether it is unlocked.",
        "If requested_action is metrics and slate_id is known, call get_player_sb_metrics (and get_optimal_pct) with that slate_id. Return projection, salary, value, SB OWN%, leverage, ceiling, floor, Optimal% where available.",
        "If requested_action is optimizer and sport/platform/slate_id are known, call build_optimizer_lineup. Confirm the context, then return the lineup. Do not show a generic menu.",
        "When the customer changes one value (e.g. \"use FanDuel\"), update only that value.",
        "Be decisive and context-aware. Lead with the known DraftKings/FanDuel + sport + slate.",
    ]
    missing_line = (
        "MISSING (ask only these): " + ", ".join(missing)
        if missing
        else "MISSING: none. Do not ask for sport, platform, or slate."
    )
    known_block = "\n".join(f"- {line}" for line in known_lines) or "- (empty)"
    return (
        "KNOWN SESSION STATE:\n"
        f"{known_block}\n"
        f"{missing_line}\n"
        "RULES:\n"
        + "\n".join(f"- {r}" for r in rules)
    )


def build_suggested_actions(ctx: ConversationContext) -> list[SuggestedAction]:
    if not ctx.sport and not ctx.platform and not ctx.slate_id:
        return []
    lock_name = ctx.locked_players[0].name if ctx.locked_players else None
    href = build_optimizer_handoff_href(ctx)
    actions = [
        SuggestedAction(id="build_lineup", label="Build lineup", prompt="Build it"),
        SuggestedAction(
            id="lock_player",
            label="Lock player",
            prompt=f"Lock {lock_name}" if lock_name else "Lock this player on the selected slate",
        ),
        SuggestedAction(
            id="compare",
            label="Compare projections",
            prompt="Compare projections for this slate",
        ),
        SuggestedAction(id="open_optimizer", label="Open optimizer", href=href),
    ]
    return actions


def build_optimizer_handoff_href(ctx: ConversationContext) -> str:
    from urllib.parse import urlencode
    params: dict[str, str] = {}
    if ctx.sport:
        params["sport"] = ctx.sport
    if ctx.platform:
        params["platform"] = ctx.platform
    if ctx.slate_id:
        params["slate"] = str(ctx.slate_id)
    if ctx.locked_players:
        params["lock"] = ",".join(p.name for p in ctx.locked_players)
    qs = urlencode(params)
    return f"/optimizer?{qs}" if qs else "/optimizer"


def fill_tool_arguments(name: str, arguments: dict, ctx: ConversationContext) -> dict:
    """Inject known session values when the model omits them."""
    args = dict(arguments or {})
    slate_tools = {
        "get_slate_players", "get_player_sb_metrics", "get_optimal_pct",
        "get_player_last_n", "resolve_player_on_slate", "build_optimizer_lineup",
    }
    if ctx.slate_id and name in slate_tools and args.get("slate_id") in (None, "", 0):
        args["slate_id"] = ctx.slate_id
    if ctx.platform and args.get("platform") in (None, ""):
        if name in slate_tools | {"get_current_slates"}:
            args["platform"] = ctx.platform
    if ctx.sport and args.get("sport") in (None, ""):
        args["sport"] = ctx.sport
    if name == "build_optimizer_lineup":
        if "locked_player_ids" not in args or not args.get("locked_player_ids"):
            args["locked_player_ids"] = [
                p.player_id or p.name for p in ctx.locked_players
            ]
        if "excluded_player_ids" not in args or not args.get("excluded_player_ids"):
            args["excluded_player_ids"] = [
                p.player_id or p.name for p in ctx.excluded_players
            ]
    if name == "resolve_player_on_slate" and not args.get("player_name") and ctx.locked_players:
        args["player_name"] = ctx.locked_players[0].name
    if name == "get_player_sb_metrics" and not args.get("player_name") and ctx.locked_players:
        args["player_name"] = ctx.locked_players[0].name
    return args
