"""
ESPN RSS Sports News — fetch, normalize, deduplicate, persist.

No external dependencies (stdlib xml.etree only).
Read-only query layer for AI and frontend.
"""

from __future__ import annotations

import hashlib
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from models.domain import ESPNNewsItem

logger = logging.getLogger(__name__)

FEEDS = {
    "MLB":    "https://www.espn.com/espn/rss/mlb/news",
    "NFL":    "https://www.espn.com/espn/rss/nfl/news",
    "NBA":    "https://www.espn.com/espn/rss/nba/news",
    "NHL":    "https://www.espn.com/espn/rss/nhl/news",
    "NCAAF":  "https://www.espn.com/espn/rss/ncf/news",
    "NCAAB":  "https://www.espn.com/espn/rss/ncb/news",
    "Soccer": "https://www.espn.com/espn/rss/soccer/news",
    "General":"https://www.espn.com/espn/rss/news",
}

MAX_ITEMS_PER_FEED = 15
RETENTION_HOURS = 24


# ── Fetch (stdlib only) ────────────────────────────────────

def _clean_html(html: str) -> str:
    text = re.sub(r'<[^>]+>', ' ', html or '')
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:500]


def _parse_rss_date(date_str: str) -> Optional[datetime]:
    """Parse RFC-2822 date string (e.g. 'Wed, 26 Aug 2026 10:13:14 EST')."""
    if not date_str:
        return None
    from email.utils import parsedate_to_datetime
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        return None


async def _fetch_rss(url: str) -> list[dict]:
    """Fetch and parse RSS feed via stdlib."""
    import urllib.request
    entries = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SB-ME-AI/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            tree = ET.parse(resp)
        root = tree.getroot()
        for item in root.findall(".//item")[:MAX_ITEMS_PER_FEED]:
            guid = item.findtext("guid") or item.findtext("link") or ""
            title = (item.findtext("title") or "").strip()
            link = item.findtext("link") or ""
            desc = _clean_html(item.findtext("description") or "")
            pub = _parse_rss_date(item.findtext("pubDate") or "")
            if not guid:
                guid = hashlib.sha256((title + link).encode()).hexdigest()[:32]
            entries.append({
                'guid': guid,
                'article_url': link,
                'headline': title,
                'summary': desc[:500],
                'published_at': pub,
            })
    except Exception as e:
        logger.warning(f"RSS fetch failed for {url}: {e}")
    return entries


async def fetch_espn_news(sport: Optional[str] = None) -> list[dict]:
    feeds_to_fetch = {sport: FEEDS[sport]} if sport and sport in FEEDS else FEEDS
    results = []
    seen = set()
    for sp, url in feeds_to_fetch.items():
        for entry in await _fetch_rss(url):
            if entry['guid'] in seen:
                continue
            seen.add(entry['guid'])
            entry['sport'] = sp
            entry['source'] = 'ESPN'
            results.append(entry)
    return results


async def sync_espn_news(db: AsyncSession) -> int:
    entries = await fetch_espn_news()
    if not entries:
        return 0
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=RETENTION_HOURS)
    new_count = 0
    for entry in entries:
        if entry['published_at'] and entry['published_at'] < cutoff:
            continue
        try:
            stmt = pg_insert(ESPNNewsItem).values(
                guid=entry['guid'],
                article_url=entry['article_url'],
                headline=entry['headline'],
                summary=entry['summary'][:500] if entry['summary'] else None,
                published_at=entry['published_at'],
                sport=entry['sport'],
                source='ESPN',
                ingested_at=now,
            ).on_conflict_do_update(
                constraint='espn_news_items_guid_key',
                set_={'headline': entry['headline'], 'summary': entry['summary'][:500] if entry['summary'] else None, 'ingested_at': now}
            )
            await db.execute(stmt)
            new_count += 1
        except Exception as e:
            logger.warning(f"Upsert failed for {entry['guid']}: {e}")
    stale_r = await db.execute(select(ESPNNewsItem).where(ESPNNewsItem.ingested_at < cutoff))
    for item in stale_r.scalars().all():
        item.stale = True
    try:
        await db.commit()
    except Exception:
        await db.rollback()
    logger.info(f"ESPN news synced: {new_count} entries")
    return new_count


# ── Query ──────────────────────────────────────────────────

async def get_news(db: AsyncSession, *, sport=None, limit=20, freshness_hours=None, query=None) -> list[dict]:
    q = select(ESPNNewsItem).where(ESPNNewsItem.stale == False)
    if sport:
        q = q.where(ESPNNewsItem.sport == sport.upper() if sport.upper() in FEEDS else sport.title())
    if freshness_hours:
        since = datetime.now(timezone.utc) - timedelta(hours=freshness_hours)
        q = q.where(ESPNNewsItem.published_at >= since)
    q = q.order_by(ESPNNewsItem.published_at.desc().nulls_last()).limit(min(limit, 50))
    r = await db.execute(q)
    items = r.scalars().all()
    results = []
    for item in items:
        if query:
            ql = query.lower()
            if ql not in (item.headline or '').lower() and ql not in (item.summary or '').lower():
                continue
        results.append({
            'guid': item.guid, 'headline': item.headline, 'summary': item.summary,
            'published_at': item.published_at.isoformat() if item.published_at else None,
            'sport': item.sport, 'source': item.source, 'article_url': item.article_url,
            'freshness': _freshness_label(item.published_at),
        })
    return results


def _freshness_label(published_at: Optional[datetime]) -> str:
    if not published_at:
        return "Unknown"
    delta = datetime.now(timezone.utc) - published_at
    if delta < timedelta(minutes=15):
        return "Just now"
    if delta < timedelta(hours=1):
        return f"{int(delta.total_seconds()/60)}m ago"
    if delta < timedelta(hours=24):
        return f"{int(delta.total_seconds()/3600)}h ago"
    return f"{delta.days}d ago"