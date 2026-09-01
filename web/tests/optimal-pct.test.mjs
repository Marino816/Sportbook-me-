import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const src = readFileSync(join(root, "src/lib/optimal-pct.ts"), "utf8");
const api = readFileSync(join(root, "src/lib/api.ts"), "utf8");
const optimizer = readFileSync(join(root, "src/app/optimizer/page.tsx"), "utf8");

const JOB_STATUSES = new Set([
  "NOT_RUN", "QUEUED", "RUNNING", "COMPLETE", "FAILED", "LOCKED", "UNKNOWN",
]);

function normalizeOptName(n) {
  return (n || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "")
    .trim();
}

function mapOptimalPctPlayers(players) {
  const m = {};
  for (const p of players || []) {
    if (p == null || p.optimal_pct == null) continue;
    const val = Number(p.optimal_pct);
    if (!Number.isFinite(val)) continue;
    const nm = normalizeOptName(p.name || "");
    if (nm) m[nm] = val;
    if (p.player_id != null && String(p.player_id)) m[String(p.player_id)] = val;
  }
  return m;
}

function lookupOptimalPct(map, namesOrIds) {
  for (const key of namesOrIds) {
    if (key == null || key === "") continue;
    const raw = map[String(key)];
    if (raw != null) return raw;
    const byName = map[normalizeOptName(String(key))];
    if (byName != null) return byName;
  }
  return null;
}

function readJobStatus(res) {
  const candidates = [res?.data?.status, res?.data?.data?.status];
  for (const raw of candidates) {
    if (typeof raw !== "string") continue;
    const up = raw.trim().toUpperCase();
    if (JOB_STATUSES.has(up)) return up;
  }
  return "NOT_RUN";
}

function readPlayers(res) {
  const a = res?.data?.result?.players;
  const b = res?.data?.data?.result?.players;
  if (Array.isArray(a)) return a;
  if (Array.isArray(b)) return b;
  return null;
}

function mapOptimalPctResponse(res) {
  const players = readPlayers(res);
  let status = readJobStatus(res);
  if (status !== "LOCKED" && Array.isArray(players) && players.length > 0) {
    status = "COMPLETE";
  }
  if (status !== "COMPLETE") return { status, map: {} };
  return { status, map: mapOptimalPctPlayers(players) };
}

function formatOptPctCell(optPct, status) {
  if (optPct != null && Number.isFinite(Number(optPct))) {
    return `${Number(optPct).toFixed(1)}%`;
  }
  const s = (status || "").trim().toUpperCase();
  if (s === "QUEUED" || s === "RUNNING") return "Calculating…";
  return "—";
}

const coleComplete = {
  status: "success",
  data: {
    slate_id: 57,
    platform: "draftkings",
    sport: "MLB",
    status: "COMPLETE",
    result: {
      players: [
        { player_id: "GERRIT_COLE_1_MLB", name: "Gerrit Cole", optimal_pct: 38.0, appearances: 190 },
        { player_id: "JESUS_LUZARDO_1_MLB", name: "Jesús Luzardo", optimal_pct: 18.5 },
      ],
    },
  },
};

test("customer Optimal% source is GET /optimal-pct", () => {
  assert.match(api, /`\/optimal-pct\?\$\{params\.toString\(\)\}`/);
  assert.match(api, /cache:\s*["']no-store["']/);
  assert.match(src, /GET \/api\/optimal-pct/);
  assert.match(optimizer, /fetchOptimalPct/);
  assert.match(optimizer, /formatOptPctCell/);
  assert.match(optimizer, /setInterval\(load, POLL_MS\)/);
});

test("COMPLETE Optimal% response renders actual player optimal_pct", () => {
  const mapped = mapOptimalPctResponse(coleComplete);
  assert.equal(mapped.status, "COMPLETE");
  const optPct = lookupOptimalPct(mapped.map, ["Gerrit Cole"]);
  assert.equal(optPct, 38.0);
  assert.equal(formatOptPctCell(optPct, mapped.status), "38.0%");
});

test("COMPLETE + player absent renders em dash", () => {
  const mapped = mapOptimalPctResponse(coleComplete);
  const optPct = lookupOptimalPct(mapped.map, ["Ryan Weathers", "unknown-id"]);
  assert.equal(optPct, null);
  assert.equal(formatOptPctCell(optPct, "COMPLETE"), "—");
});

test("QUEUED and RUNNING render Calculating", () => {
  for (const status of ["QUEUED", "RUNNING"]) {
    const mapped = mapOptimalPctResponse({ data: { status, result: null } });
    assert.equal(mapped.status, status);
    assert.deepEqual(mapped.map, {});
    assert.equal(formatOptPctCell(null, status), "Calculating…");
  }
});

test("FAILED NOT_RUN LOCKED cannot remain Calculating", () => {
  for (const status of ["FAILED", "NOT_RUN", "LOCKED", "UNKNOWN"]) {
    const mapped = mapOptimalPctResponse({ data: { status, result: null } });
    assert.equal(mapped.status, status);
    assert.equal(formatOptPctCell(null, status), "—");
    assert.notEqual(formatOptPctCell(null, status), "Calculating…");
  }
});

test("maps COMPLETE envelope players by player_id", () => {
  const mapped = mapOptimalPctResponse(coleComplete);
  assert.equal(lookupOptimalPct(mapped.map, ["GERRIT_COLE_1_MLB"]), 38.0);
  assert.equal(lookupOptimalPct(mapped.map, [12345]), null);
  assert.equal(lookupOptimalPct(mapped.map, ["12345", "GERRIT_COLE_1_MLB"]), 38.0);
});

test("normalized-name fallback matches accented SGO names", () => {
  const mapped = mapOptimalPctResponse(coleComplete);
  assert.equal(lookupOptimalPct(mapped.map, ["Jesús Luzardo"]), 18.5);
  assert.equal(lookupOptimalPct(mapped.map, ["Jesus Luzardo"]), 18.5);
  assert.equal(normalizeOptName("Jesús Luzardo"), "jesusluzardo");
});

test("players in payload are treated as COMPLETE even if status field is stale", () => {
  const mapped = mapOptimalPctResponse({
    status: "success",
    data: {
      status: "RUNNING",
      result: { players: [{ player_id: "GERRIT_COLE_1_MLB", name: "Gerrit Cole", optimal_pct: 56.8 }] },
    },
  });
  assert.equal(mapped.status, "COMPLETE");
  assert.equal(lookupOptimalPct(mapped.map, ["Gerrit Cole", "GERRIT_COLE_1_MLB"]), 56.8);
  assert.equal(formatOptPctCell(56.8, mapped.status), "56.8%");
});

test("does not treat wrap status success as COMPLETE", () => {
  const mapped = mapOptimalPctResponse({
    status: "success",
    data: { status: "NOT_RUN", result: null },
  });
  assert.equal(mapped.status, "NOT_RUN");
  assert.deepEqual(mapped.map, {});
  assert.equal(formatOptPctCell(null, mapped.status), "—");
});

test("COMPLETE with empty players does not invent Optimal%", () => {
  const mapped = mapOptimalPctResponse({
    data: { status: "COMPLETE", result: { players: [] } },
  });
  assert.equal(mapped.status, "COMPLETE");
  assert.deepEqual(mapped.map, {});
  assert.equal(lookupOptimalPct(mapped.map, ["Aaron Judge", "own40", 2.1]), null);
  assert.equal(formatOptPctCell(null, "COMPLETE"), "—");
});

test("never substitutes ownership, leverage, or projection", () => {
  const mapped = mapOptimalPctResponse({
    data: {
      status: "COMPLETE",
      result: {
        players: [{
          player_id: "1",
          name: "Judge",
          optimal_pct: 11,
          sbme_ownership_pct: 40,
          leverage: 2.1,
          projected_fp: 12.5,
        }],
      },
    },
  });
  assert.equal(lookupOptimalPct(mapped.map, ["Judge"]), 11);
  assert.notEqual(lookupOptimalPct(mapped.map, ["Judge"]), 40);
  assert.notEqual(lookupOptimalPct(mapped.map, ["Judge"]), 2.1);
});

test("helper source indexes player_id and optimal_pct only", () => {
  const code = src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
  assert.match(code, /p\.player_id/);
  assert.match(code, /p\.optimal_pct/);
  assert.match(code, /formatOptPctCell/);
  assert.doesNotMatch(code, /sbme_ownership_pct/);
  assert.doesNotMatch(code, /projected_fp/);
});
