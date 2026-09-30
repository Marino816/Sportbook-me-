"""The Odds API key for isolated Market Tools snapshot work. Never logs the key."""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

ENV_NAME = "ODDS_API_KEY"
PRIVATE_DIR = Path.home() / ".sbme-dev" / "odds-api"
PRIVATE_ENV = PRIVATE_DIR / ".env"
BACKEND_ENV = Path(__file__).resolve().parents[2] / ".env"


def _parse_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text().splitlines():
        if not line.strip() or line.strip().startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        out[name.strip()] = value.strip().strip('"').strip("'")
    return out


def load_key() -> str | None:
    env = (os.environ.get(ENV_NAME) or "").strip()
    if env and not env.startswith("your_"):
        return env
    for path in (PRIVATE_ENV, BACKEND_ENV):
        value = _parse_env(path).get(ENV_NAME, "").strip()
        if value and not value.startswith("your_"):
            return value
    return None


def _read_hidden() -> str:
    if sys.stdin.isatty():
        import getpass

        return getpass.getpass("ODDS_API_KEY (hidden): ").strip()
    script = (
        'text returned of (display dialog '
        '"Enter The Odds API key for isolated Market Tools development. Input is hidden." '
        'default answer "" with hidden answer '
        'with title "SB ME Odds API key")'
    )
    proc = subprocess.run(
        ["osascript", "-e", script],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return ""
    return (proc.stdout or "").strip()


def store_key(value: str) -> Path:
    PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(PRIVATE_DIR, stat.S_IRWXU)
    text = f"{ENV_NAME}={value}\n"
    PRIVATE_ENV.write_text(text)
    os.chmod(PRIVATE_ENV, stat.S_IRUSR | stat.S_IWUSR)
    return PRIVATE_ENV


def main() -> int:
    existing = load_key()
    if existing:
        print("stored_name=ODDS_API_KEY source=existing_local_store printed=false")
        return 0
    key = _read_hidden()
    if not key or "\n" in key or "\r" in key or key.startswith("your_"):
        print("REFUSED: empty or invalid key. File unchanged.", file=sys.stderr)
        return 2
    store_key(key)
    print("stored_name=ODDS_API_KEY path=~/.sbme-dev/odds-api/.env mode=600 printed=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
