"""SportsDataIO API client — auth, retry, rate limiting."""
import os
import time
import json
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE_URL = "https://api.sportsdata.io/v3/mlb"
CALL_LIMIT = 5000  # monthly trial limit
_call_count = 0


def _api_key() -> str:
    key = os.environ.get("SPORTSDATAIO_API_KEY")
    if not key:
        raise RuntimeError("SPORTSDATAIO_API_KEY not set")
    return key


def remaining_calls() -> int:
    return max(0, CALL_LIMIT - _call_count)


def _get(path: str, params: dict = None) -> dict:
    """Authenticated GET with retry and rate-limiting."""
    global _call_count
    if _call_count >= CALL_LIMIT:
        raise RuntimeError("Monthly API call limit reached")

    url = BASE_URL + path
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url += "?" + qs

    req = Request(url)
    req.add_header("Ocp-Apim-Subscription-Key", _api_key())

    last_err = None
    for attempt in range(3):
        try:
            res = urlopen(req, timeout=15)
            _call_count += 1
            return json.loads(res.read())
        except HTTPError as e:
            last_err = e
            body = e.read().decode()[:300] if e.fp else ""
            if e.code == 429:
                time.sleep(2 ** attempt)
                continue
            if e.code == 401:
                raise RuntimeError("SportsDataIO: unauthorized — check API key")
            raise RuntimeError(f"SportsDataIO HTTP {e.code}: {body}")
        except URLError as e:
            last_err = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"SportsDataIO unreachable after 3 retries: {last_err}")


def fetch(endpoint: str, params: dict = None) -> dict:
    """Fetch data from SportsDataIO. Returns parsed JSON."""
    return _get(endpoint, params)


class IngestionMetrics:
    """Track ingestion runs for monitoring."""

    started_at: datetime | None = None
    finished_at: datetime | None = None
    records_ingested: int = 0
    errors: list[str] = []
    data_mode: str = "TRIAL_SCRAMBLED"

    @classmethod
    def start(cls, label: str):
        cls.started_at = datetime.now(timezone.utc)
        cls.records_ingested = 0
        cls.errors = []

    @classmethod
    def finish(cls):
        cls.finished_at = datetime.now(timezone.utc)

    @classmethod
    def summary(cls) -> dict:
        return {
            "started": str(cls.started_at),
            "finished": str(cls.finished_at),
            "records": cls.records_ingested,
            "errors": cls.errors,
            "api_calls": _call_count,
            "data_mode": cls.data_mode,
        }