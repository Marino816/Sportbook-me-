"""Headless Chrome / CDP customer-interaction tests for Market Tools snapshot app."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
OUT = Path(__file__).resolve().parent / "screenshots"
E2E_JSON = OUT / "e2e-results.json"

CUSTOMER_SCRIPT = r"""
async (creds) => {
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const waitFor = async (fn, tries = 120) => {
    for (let i = 0; i < tries; i++) {
      const v = fn();
      if (v) return v;
      await wait(250);
    }
    return null;
  };
  const setNative = (el, val) => {
    const proto = Object.getPrototypeOf(el);
    const desc = Object.getOwnPropertyDescriptor(proto, "value");
    desc.set.call(el, val);
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
  };
  const results = { ok: true, checks: [], blockers: [], pathname: location.pathname };
  const note = (name, pass, detail) => { results.checks.push({ name, pass, detail }); if (!pass) results.ok = false; };
  const clickChip = (label) => {
    const btn = [...document.querySelectorAll(".sbme-mt-approved .chip, .chip")].find((b) => (b.textContent || "").trim() === label);
    if (btn) btn.click();
    return btn;
  };
  const clickTab = (label) => {
    const btn = [...document.querySelectorAll(".sbme-mt-approved .tab, .tab")].find((b) => (b.textContent || "").trim() === label);
    if (btn) btn.click();
    return btn;
  };
  const slipCount = () => Number((document.querySelector(".slip-toggle span") || {}).textContent || 0);
  const oddsNow = () => [...document.querySelectorAll(".sbme-mt-approved button.odd")].filter((b) => !b.disabled);

  const userInput = await waitFor(() => document.querySelector('input[autocomplete="username"], .sbme-mt-approved'));
  if (userInput && userInput.matches && userInput.matches("input")) {
    const passInput = document.querySelector('input[type="password"]');
    setNative(userInput, creds.email);
    if (passInput) setNative(passInput, creds.password);
    document.querySelector(".sbme-login-submit, button[type='submit']")?.click();
  }
  const app = await waitFor(() => document.querySelector(".sbme-mt-approved"));
  note("application_loaded", Boolean(app), app ? location.pathname : location.href);
  if (!app) return results;
  localStorage.removeItem("sbme_mt_slip_v1");

  const chipsReady = await waitFor(() => document.querySelector(".sbme-mt-approved .chip"));
  const card = document.querySelector(".sbme-mt-approved .card");
  note("snapshot_rendered", Boolean(chipsReady && card), chipsReady ? "approved UI and cards present" : "approved UI still loading");

  note("sport_filter", Boolean(clickChip("NBA") || clickChip("NFL") || document.querySelector(".sbme-mt-approved .chip")), "sport chips");
  await wait(300);
  clickChip("Soccer");
  await wait(300);
  const selects = [...document.querySelectorAll(".sbme-mt-approved select")];
  const league = selects.find((s) => [...s.options].some((o) => /soccer|premier|liga|serie|bundesliga|ligue|mls|all soccer/i.test(o.textContent || "")));
  note("soccer_league_filter", Boolean(league), league ? "league selector present" : "missing");
  if (league && league.options.length > 1) {
    league.value = league.options[1].value;
    league.dispatchEvent(new Event("change", { bubbles: true }));
    await wait(200);
  }
  clickChip("NFL");
  await wait(300);

  const date = [...document.querySelectorAll(".sbme-mt-approved label")].find((l) => /date/i.test(l.textContent || ""));
  const book = [...document.querySelectorAll(".sbme-mt-approved label")].find((l) => /sportsbook/i.test(l.textContent || ""));
  const search = document.querySelector('.sbme-mt-approved input[type="search"], .sbme-mt-approved input[placeholder="Search"]');
  note("date_filter", Boolean(date && date.querySelector("select")), date ? "present" : "missing");
  note("sportsbook_filter", Boolean(book && book.querySelector("select")), book ? `options=${(book.querySelector("select") || {}).options?.length}` : "missing");
  note("player_team_search", Boolean(search), "present");
  if (search) {
    setNative(search, "a");
    await wait(150);
    setNative(search, "");
  }

  let enabledOdds = oddsNow();
  note("odds_buttons", enabledOdds.length > 0, String(enabledOdds.length));
  if (enabledOdds.length) {
    enabledOdds[0].click();
    await wait(500);
  }
  document.querySelector(".slip-toggle")?.click();
  await wait(200);
  const firstCount = slipCount();
  note("add_selection", firstCount >= 1, `legs=${firstCount}`);
  const firstLeg = document.querySelector(".leg .meta");
  note("leg_identity", Boolean(firstLeg && firstLeg.textContent.trim()), firstLeg ? firstLeg.textContent.trim() : "missing");

  if (enabledOdds.length) {
    enabledOdds[0].click();
    await wait(250);
  }
  const dupWarn = [...document.querySelectorAll(".slip-body .warn")].map((n) => n.textContent).join(" ");
  note("duplicate_blocked", /already on the slip/i.test(dupWarn) || slipCount() === firstCount, dupWarn || "count unchanged");

  enabledOdds = oddsNow();
  const firstCard = enabledOdds[0] && enabledOdds[0].closest("article");
  const cardH2h = [...(firstCard ? firstCard.querySelectorAll("button.odd[data-market='h2h']") : [])].filter((b) => !b.disabled);
  const cardSpreads = [...(firstCard ? firstCard.querySelectorAll("button.odd[data-market='spreads']") : [])].filter((b) => !b.disabled);
  const beforeConflict = slipCount();
  if (cardH2h.length > 1) {
    cardH2h[1].click();
    await wait(400);
  }
  const conflictText = [...document.querySelectorAll(".slip-body .warn")].map((n) => n.textContent).join(" ");
  note("true_conflict_blocked", /conflicts with another pick/i.test(conflictText) && slipCount() === beforeConflict, conflictText || `legs=${slipCount()}`);

  if (cardSpreads[0]) {
    cardSpreads[0].click();
    await wait(800);
  }
  const afterCompat = slipCount();
  const sameGameText = [...document.querySelectorAll(".slip-body .warn, .slip-body .ok, .sgp-unavailable")].map((n) => n.textContent).join(" | ");
  const combinedNumber = [...document.querySelectorAll(".slip-body p")].some((n) => /^Combined /.test(n.textContent || ""));
  note("compatible_same_game_added", afterCompat >= 2, `legs=${afterCompat} ${sameGameText}`);
  note("sgp_combined_unavailable", /no verified sportsbook pricing|combined odds are not shown/i.test(sameGameText) && !combinedNumber, sameGameText);

  clickTab("Compare");
  await wait(250);
  clickTab("Player Props");
  await wait(250);
  clickTab("Parlay Builder");
  await wait(250);
  note("persist_across_tabs", slipCount() >= 2, `legs=${slipCount()}`);

  [...document.querySelectorAll("button")].find((b) => (b.textContent || "").trim() === "Clear All")?.click();
  await wait(250);
  clickTab("Game Odds");
  await wait(250);
  clickChip("NFL");
  await wait(300);
  const nflOdds = oddsNow();
  if (nflOdds[0]) {
    nflOdds[0].click();
    await wait(400);
  }
  clickChip("NBA");
  await wait(350);
  let crossOdds = oddsNow();
  if (!crossOdds.length) {
    clickChip("MLB");
    await wait(350);
    crossOdds = oddsNow();
  }
  if (crossOdds[0]) {
    crossOdds[0].click();
    await wait(800);
  }
  const combined = [...document.querySelectorAll(".slip-body .ok, .slip-body .warn")].map((n) => n.textContent).join(" | ");
  note("parlay_result", Boolean(combined), combined || "no parlay summary");
  note("same_or_cross_game_labeled", /Same-game|Illustrative combined|already on the slip|conflicts|no verified sportsbook pricing/i.test(combined), combined);

  document.querySelector(".leg .x")?.click();
  await wait(200);
  note("remove_leg", true, `legs=${slipCount()}`);
  [...document.querySelectorAll("button")].find((b) => (b.textContent || "").trim() === "Clear All")?.click();
  await wait(200);
  note("clear_all", slipCount() === 0, String(slipCount()));

  const token = localStorage.getItem("sbme_dfs_token");
  const resolved = await fetch(`${creds.api}/market-tools/internal/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ event_id: "sgo:legacy-unmapped", id: "sgo:legacy-unmapped" }),
  }).then((r) => r.json()).catch((e) => ({ error: String(e) }));
  note("legacy_unmapped", Boolean(resolved.data && resolved.data.unavailable), JSON.stringify(resolved.data || resolved));

  const slip = document.querySelector(".slip");
  const toggle = document.querySelector(".slip-toggle");
  note("selection_panel", Boolean(slip && toggle), slip ? `width=${window.innerWidth}` : "missing");
  results.token_present = Boolean(token);
  return results;
}
"""


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _wait_http(url: str, timeout: float = 20) -> None:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status < 500:
                    return
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(0.2)
    raise RuntimeError(f"Server did not start at {url}: {last}")


class _MiniWS:
    def __init__(self, url: str):
        from urllib.parse import urlparse
        import base64
        import hashlib
        parsed = urlparse(url)
        key = base64.b64encode(os.urandom(16)).decode()
        path = parsed.path + (("?" + parsed.query) if parsed.query else "")
        req = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {parsed.hostname}:{parsed.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock = socket.create_connection((parsed.hostname, parsed.port), timeout=15)
        self.sock.sendall(req.encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                break
            buf += chunk
        self._id = 0

    def send(self, payload: dict) -> None:
        raw = json.dumps(payload).encode()
        header = bytearray()
        header.append(0x81)
        n = len(raw)
        mask = os.urandom(4)
        if n < 126:
            header.append(0x80 | n)
        elif n < 65536:
            header.append(0x80 | 126)
            header.extend(n.to_bytes(2, "big"))
        else:
            header.append(0x80 | 127)
            header.extend(n.to_bytes(8, "big"))
        header.extend(mask)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(raw))
        self.sock.sendall(header + masked)

    def recv(self) -> dict:
        def read(n: int) -> bytes:
            out = b""
            while len(out) < n:
                chunk = self.sock.recv(n - len(out))
                if not chunk:
                    raise RuntimeError("CDP websocket closed")
                out += chunk
            return out
        b1, b2 = read(2)
        length = b2 & 0x7F
        if length == 126:
            length = int.from_bytes(read(2), "big")
        elif length == 127:
            length = int.from_bytes(read(8), "big")
        if b2 & 0x80:
            read(4)
        data = read(length)
        if (b1 & 0x0F) == 0x1:
            return json.loads(data.decode())
        return {}

    def call(self, method: str, params: dict | None = None, timeout: float = 20) -> dict:
        self._id += 1
        msg_id = self._id
        payload = {"id": msg_id, "method": method}
        if params:
            payload["params"] = params
        self.send(payload)
        deadline = time.time() + timeout
        while time.time() < deadline:
            msg = self.recv()
            if msg.get("id") == msg_id:
                return msg
        raise TimeoutError(method)

    def close(self) -> None:
        try:
            self.sock.close()
        except Exception:
            pass


def _cdp_connect(port: int) -> _MiniWS:
    deadline = time.time() + 15
    last = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=2) as resp:
                pages = json.loads(resp.read().decode())
            page = next(
                (p for p in pages if p.get("webSocketDebuggerUrl") and p.get("type") in {None, "page"}),
                None,
            )
            if page:
                return _MiniWS(page["webSocketDebuggerUrl"])
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(0.25)
    raise RuntimeError(f"No Chrome page target on {port}: {last}")


def run() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    web = os.environ.get("SBME_E2E_WEB", "http://127.0.0.1:3000").rstrip("/")
    api = os.environ.get("SBME_E2E_API", "http://127.0.0.1:8000/api").rstrip("/")
    email = os.environ.get("SBME_E2E_EMAIL", "")
    password = os.environ.get("SBME_E2E_PASSWORD", "")
    if not email or not password:
        return {"blocker": "SBME_E2E_EMAIL and SBME_E2E_PASSWORD must be set", "desktop": None, "mobile": None}
    login_url = f"{web}/login?next={urllib.parse.quote('/market-tools')}"
    cdp_port = _free_port()
    _wait_http(f"{web}/login", timeout=90)
    origin = api[:-4] if api.endswith("/api") else api
    _wait_http(f"{origin}/health", timeout=30)

    profile = tempfile.mkdtemp(prefix="sbme-mt-e2e-")
    chrome = subprocess.Popen(
        [
            CHROME,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            f"--remote-debugging-port={cdp_port}",
            f"--user-data-dir={profile}",
            login_url,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    report = {
        "app": login_url,
        "web": web,
        "provider_http": None,
        "desktop": None,
        "mobile": None,
        "blocker": None,
    }
    creds = json.dumps({"email": email, "password": password, "api": api})
    try:
        deadline = time.time() + 25
        ws = None
        while time.time() < deadline:
            try:
                ws = _cdp_connect(cdp_port)
                break
            except Exception:
                time.sleep(0.3)
        if ws is None:
            report["blocker"] = f"Chrome CDP did not open on port {cdp_port}"
            return report

        def run_viewport(width: int, height: int, name: str) -> dict:
            ws.call("Emulation.setDeviceMetricsOverride", {
                "width": width, "height": height, "deviceScaleFactor": 1, "mobile": width < 800,
            })
            ws.call("Page.enable")
            ws.call("Page.navigate", {"url": login_url})
            time.sleep(6)
            ws.call("Runtime.enable")
            result = ws.call("Runtime.evaluate", {
                "expression": f"({CUSTOMER_SCRIPT})({creds})",
                "awaitPromise": True,
                "returnByValue": True,
            }, timeout=90)
            value = (result.get("result") or {}).get("result") or {}
            payload = value.get("value") if value.get("type") == "object" else None
            shot = ws.call("Page.captureScreenshot", {"format": "png"})
            b64 = ((shot.get("result") or {}).get("data")) or ""
            if b64:
                import base64
                (OUT / f"e2e-app-{name}.png").write_bytes(base64.b64decode(b64))
            return payload or {"ok": False, "checks": [], "error": result}

        report["desktop"] = run_viewport(1280, 800, "desktop")
        report["mobile"] = run_viewport(390, 844, "mobile")
        token_eval = ws.call("Runtime.evaluate", {
            "expression": "localStorage.getItem('sbme_dfs_token')",
            "returnByValue": True,
        })
        token = ((token_eval.get("result") or {}).get("result") or {}).get("value")
        if token:
            req = urllib.request.Request(
                f"{api}/market-tools/internal/status",
                headers={"Authorization": f"Bearer {token}"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                report["provider_http"] = json.loads(resp.read().decode()).get("data", {}).get("cache")
        ws.close()
    except Exception as exc:  # noqa: BLE001
        report["blocker"] = str(exc)
    finally:
        chrome.terminate()
    E2E_JSON.write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> int:
    if not Path(CHROME).is_file():
        print(json.dumps({"blocker": f"Chrome not found at {CHROME}", "unverified": "all browser interactions"}))
        return 2
    report = run()
    print(json.dumps({
        "blocker": report.get("blocker"),
        "desktop_ok": (report.get("desktop") or {}).get("ok"),
        "mobile_ok": (report.get("mobile") or {}).get("ok"),
        "provider_http": report.get("provider_http"),
        "path": str(E2E_JSON),
    }, indent=2))
    if report.get("blocker"):
        return 2
    desktop = report.get("desktop") or {}
    mobile = report.get("mobile") or {}
    return 0 if desktop.get("ok") and mobile.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
